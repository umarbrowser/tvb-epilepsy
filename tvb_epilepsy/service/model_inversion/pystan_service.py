import time
import os
from copy import deepcopy

import numpy as np
import pystan as ps

from tvb_epilepsy.base.utils.log_error_utils import initialize_logger, raise_not_implemented_error


LOG = initialize_logger(__name__)


class PystanService(object):

    def __init__(self, model_name=None, model=None, model_code=None, model_code_path="", fitmode="sampling", logger=LOG):
        self.logger = logger
        self.fit = None
        self.est = {}
        self.fitmode = fitmode
        self.model = model
        self.model_code = model_code
        self.model_code_path = model_code_path
        if isinstance(model_name, basestring) and len(model_name) > 0:
            self.model_name = model_name
        else:
            self.model_name = os.path.basename(self.model_code_path)
        self.compilation_time = 0.0
        self.fitting_time = 0.0

    def compile_stan_model(self):
        tic = time.time()
        self.logger.info("Compiling model...")
        self.model = ps.StanModel(file=self.model_code_path, model_name=self.model_name)
        self.compilation_time = time.time() - tic
        self.logger.info(str(self.compilation_time) + ' sec required to compile')

    def fit_stan_model(self, **kwargs):
        self.logger.info("Model fitting with " + self.fitmode + "...")
        tic = time.time()
        self.fit = getattr(self.model, self.fitmode)(data=self.model_data, **kwargs)
        self.fitting_time = time.time() - tic
        self.logger.info(str(self.fitting_time) + ' sec required to fit')
        if self.fitmode is "optimizing":
            self.est = deepcopy(self.fit)
            self.fit = None
        else:
            self.logger.info("Extracting estimates...")
            if self.fitmode is "sampling":
                self.est = self.fit.extract(permuted=True)
            elif self.fitmode is "vb":
                self.est = self.read_vb_results()

    def read_vb_results(self):
        self.est = {}
        for ip, p in enumerate(self.fit['sampler_param_names']):
            p_split = p.split('.')
            p_name = p_split.pop(0)
            p_name_samples = p_name + "_s"
            if self.est.get(p_name) is None:
                self.est.update({p_name_samples: []})
                self.est.update({p_name: []})
            if len(p_split) == 0:
                # scalar parameters
                self.est[p_name_samples] = self.fit["sampler_params"][ip]
                self.est[p_name] = self.fit["mean_pars"][ip]
            else:
                if len(p_split) == 1:
                    # vector parameters
                    self.est[p_name_samples].append(self.fit["sampler_params"][ip])
                    self.est[p_name].append(self.fit["mean_pars"][ip])
                else:
                    ii = int(p_split.pop(0)) - 1
                    if len(p_split) == 0:
                        # 2D matrix parameters
                        if len(self.est[p_name]) < ii + 1:
                            self.est[p_name_samples].append([self.fit["sampler_params"][ip]])
                            self.est[p_name].append([self.fit["mean_pars"][ip]])
                        else:
                            self.est[p_name_samples][ii].append(self.fit["sampler_params"][ip])
                            self.est[p_name][ii].append(self.fit["mean_pars"][ip])
                    else:
                        if len(self.est[p_name]) < ii + 1:
                            self.est[p_name_samples].append([])
                            self.est[p_name].append([])
                        jj = int(p_split.pop(0)) - 1
                        if len(p_split) == 0:
                            # 3D matrix parameters
                            if len(self.est[p_name][ii]) < jj + 1:
                                self.est[p_name_samples][ii].append([self.fit["sampler_params"][ip]])
                                self.est[p_name][ii].append([self.fit["mean_pars"][ip]])
                            else:
                                if len(self.est[p_name][ii]) < jj + 1:
                                    self.est[p_name_samples][ii].append([])
                                    self.est[p_name][ii].append([])
                                self.est[p_name_samples][ii][jj].append(self.fit["sampler_params"][ip])
                                self.est[p_name][ii][jj].append(self.fit["mean_pars"][ip])
                        else:
                            raise_not_implemented_error("Extracting of parameters of more than 3 dimensions is not " +
                                                        "implemented yet for vb!", self.logger)
        for key in self.est.keys():
            if isinstance(self.est[key], list):
                self.est[key] = np.squeeze(np.array(self.est[key]))