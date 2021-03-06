import os
import numpy as np
from copy import deepcopy

from tvb_epilepsy.base.constants import DATA_MODE, TVB
from tvb_epilepsy.base.configurations import FOLDER_RES, DATA_CUSTOM
from tvb_epilepsy.base.h5_model import convert_to_h5_model, read_h5_model
from tvb_epilepsy.base.utils import assert_equal_objects, initialize_logger
from tvb_epilepsy.base.model.model_vep import Connectivity
from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis

if DATA_MODE is TVB:
    from tvb_epilepsy.tvb_api.readers_tvb import TVBReader as Reader
else:
    from tvb_epilepsy.custom.readers_custom import CustomReader as Reader

logger = initialize_logger(__name__)

if __name__ == "__main__":

    # -------------------------------Reading data-----------------------------------

    empty_connectivity = Connectivity("", np.array([]), np.array([]))
    empty_hypothesis = DiseaseHypothesis(empty_connectivity)

    data_folder = os.path.join(DATA_CUSTOM, 'Head')

    reader = Reader()

    logger.info("Reading from: " + data_folder)
    head = reader.read_head(data_folder)

    # # Manual definition of hypothesis...:
    x0_indices = [20]
    x0_values = [0.9]
    e_indices = [70]
    e_values = [0.9]
    disease_values = x0_values + e_values
    disease_indices = x0_indices + e_indices

    # This is an example of x0_values mixed Excitability and Epileptogenicity Hypothesis:
    hyp_x0_E = DiseaseHypothesis(head.connectivity, excitability_hypothesis={tuple(x0_indices): x0_values},
                                 epileptogenicity_hypothesis={tuple(e_indices): e_values},
                                 connectivity_hypothesis={})

    obj = {"hyp_x0_E": hyp_x0_E,
           "test_dict":
               {"list0": ["l00", 1, {"d020": "a", "d021": [True, False, np.inf, np.nan, None, [], (), {}, ""]}]}}
    logger.info("\n\nOriginal object:\n" + str(obj))

    logger.info("\n\nWriting object to h5 file...")
    h5_model = convert_to_h5_model(obj)

    h5_model.write_to_h5(FOLDER_RES, "test_h5_model.h5")

    h5_model1 = read_h5_model(FOLDER_RES + "/test_h5_model.h5")
    obj1 = h5_model1.convert_from_h5_model(deepcopy(obj))

    if assert_equal_objects(obj, obj1):
        logger.info("\n\nRead identical object:\n" + str(obj1))
    else:
        logger.info("\n\nComparison failed!:\n" + str(obj1))

    h5_model2 = read_h5_model(FOLDER_RES + "/test_h5_model.h5")
    obj2 = h5_model2.convert_from_h5_model(children_dict={"DiseaseHypothesis": empty_hypothesis})

    if assert_equal_objects(obj, obj2):
        logger.info("\n\nRead object as dictionary:\n" + str(obj2))
    else:
        logger.info("\n\nComparison failed!:\n" + str(obj2))
