
import numpy as np

from tvb_epilepsy.base.constants import MAX_DISEASE_VALUE
from tvb_epilepsy.base.configurations import FOLDER_RES
from tvb_epilepsy.base.utils import initialize_logger, linear_index_to_coordinate_tuples, \
    dicts_of_lists_to_lists_of_dicts, list_of_dicts_to_dicts_of_ndarrays
from tvb_epilepsy.service.sampling_service import StochasticSamplingService
from tvb_epilepsy.service.pse_service import PSEService
from tvb_epilepsy.scripts.hypothesis_scripts import start_lsa_run

###
# These functions are helper functions to run parameter search exploration (pse) for Linear Stability Analysis (LSA).
###
def pse_from_lsa_hypothesis(lsa_hypothesis, connectivity_matrix, region_labels,
                            n_samples, half_range=0.1, global_coupling=[],
                            healthy_regions_parameters=[],
                            model_configuration_service=None, lsa_service=None,
                            save_services=False, logger=None, **kwargs):

    if logger is None:
        logger = initialize_logger(__name__)

    all_regions_indices = range(lsa_hypothesis.number_of_regions)
    disease_indices = lsa_hypothesis.get_regions_disease_indices()
    healthy_indices = np.delete(all_regions_indices, disease_indices).tolist()

    pse_params = {"path": [], "indices": [], "name": [], "samples": []}

    # First build from the hypothesis the input parameters of the parameter search exploration.
    # These can be either originating from excitability, epileptogenicity or connectivity hypotheses,
    # or they can relate to the global coupling scaling (parameter K of the model configuration)
    for ii in range(len(lsa_hypothesis.x0_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.x0_values")
        pse_params["name"].append(str(region_labels[lsa_hypothesis.x0_indices[ii]]) + " Excitability")

        # Now generate samples using a truncated uniform distribution
        sampler = StochasticSamplingService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                            random_seed=kwargs.get("random_seed", None),
                                            trunc_limits={"high": MAX_DISEASE_VALUE},
                                            sampler="uniform",
                                            loc=lsa_hypothesis.x0_values[ii] - half_range, scale=2 * half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    for ii in range(len(lsa_hypothesis.e_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.e_values")
        pse_params["name"].append(str(region_labels[lsa_hypothesis.e_indices[ii]]) + " Epileptogenicity")

        # Now generate samples using a truncated uniform distribution
        sampler = StochasticSamplingService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                            random_seed=kwargs.get("random_seed", None),
                                            trunc_limits={"high": MAX_DISEASE_VALUE},
                                            sampler="uniform",
                                            loc=lsa_hypothesis.e_values[ii] - half_range, scale=2 * half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    for ii in range(len(lsa_hypothesis.w_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.w_values")
        inds = linear_index_to_coordinate_tuples(lsa_hypothesis.w_indices[ii], connectivity_matrix.shape)
        if len(inds) == 1:
            pse_params["name"].append(str(region_labels[inds[0][0]]) + "-" +
                                      str(region_labels[inds[0][0]]) + " Connectivity")
        else:
            pse_params["name"].append("Connectivity[" + str(inds), + "]")

        # Now generate samples using a truncated normal distribution
        sampler = StochasticSamplingService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                            random_seed=kwargs.get("random_seed", None),
                                            trunc_limits={"high": MAX_DISEASE_VALUE},
                                            sampler="norm", loc=lsa_hypothesis.w_values[ii], scale=half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    kloc = model_configuration_service.K_unscaled[0]
    for val in global_coupling:
        pse_params["path"].append("model.configuration.service.K_unscaled")
        inds = val.get("indices", all_regions_indices)
        if np.all(inds == all_regions_indices):
            pse_params["name"].append("Global coupling")
        else:
            pse_params["name"].append("Afferent coupling[" + str(inds) + "]")
        pse_params["indices"].append(inds)

        # Now generate samples susing a truncated normal distribution
        sampler = StochasticSamplingService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                            random_seed=kwargs.get("random_seed", None),
                                            trunc_limits={"low": 0.0}, sampler="norm", loc=kloc, scale=30 * half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    pse_params_list = dicts_of_lists_to_lists_of_dicts(pse_params)

    # Add a random jitter to the healthy regions if required...:
    for val in healthy_regions_parameters:
        inds = val.get("indices", healthy_indices)
        name = val.get("name", "x0_values")
        n_params = len(inds)
        sampler = StochasticSamplingService(n_samples=n_samples, n_outputs=n_params, sampler="uniform",
                                            trunc_limits={"low": 0.0}, sampling_module="scipy",
                                            random_seed=kwargs.get("random_seed", None),
                                            loc=kwargs.get("loc", 0.0), scale=kwargs.get("scale", 2 * half_range))

        samples = sampler.generate_samples(**kwargs)
        for ii in range(n_params):
            pse_params_list.append({"path": "model_configuration_service." + name, "samples": samples[ii],
                                    "indices": [inds[ii]], "name": name})

    # Now run pse service to generate output samples:

    pse = PSEService("LSA", hypothesis=lsa_hypothesis, params_pse=pse_params_list)
    pse_results, execution_status = pse.run_pse(connectivity_matrix, grid_mode=False, lsa_service_input=lsa_service,
                                                model_configuration_service_input=model_configuration_service)

    pse_results = list_of_dicts_to_dicts_of_ndarrays(pse_results)

    if save_services:
        logger.info(pse.__repr__())
        pse.write_to_h5(FOLDER_RES, "test_pse_service.h5")

    return pse_results, pse_params_list


def pse_from_hypothesis(hypothesis, connectivity_matrix, region_labels, n_samples, half_range=0.1, global_coupling=[],
                        healthy_regions_parameters=[], save_services=False, logger=None, **kwargs):

    if logger is None:
        logger = initialize_logger(__name__)

    # Compute lsa for this hypothesis before the parameter search:
    logger.info("Running hypothesis: " + hypothesis.name)
    model_configuration_service, model_configuration, lsa_service, lsa_hypothesis = \
        start_lsa_run(hypothesis, connectivity_matrix, logger)

    pse_results, pse_params_list = pse_from_lsa_hypothesis(lsa_hypothesis, connectivity_matrix, region_labels,
                                                           n_samples, half_range, global_coupling,
                                                           healthy_regions_parameters,
                                                           model_configuration_service, lsa_service,
                                                           save_services, logger, **kwargs)

    return model_configuration, lsa_service, lsa_hypothesis, pse_results, pse_params_list