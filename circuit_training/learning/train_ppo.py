# coding=utf-8
# Copyright 2021 The Circuit Training Team Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sample training with distributed collection using a variable container."""

import functools
import os
import random

from absl import app
from absl import flags
from absl import logging
from circuit_training.environment import environment
from circuit_training.learning import static_feature_cache
from circuit_training.learning import train_ppo_lib
from circuit_training.model import model
import gin
import numpy as np
import tensorflow as tf
from tf_agents.system import system_multiprocessing as multiprocessing
from tf_agents.train.utils import spec_utils
from tf_agents.train.utils import strategy_utils

_GIN_FILE = flags.DEFINE_multi_string('gin_file', None,
                                      'Paths to the gin-config files.')
_GIN_BINDINGS = flags.DEFINE_multi_string('gin_bindings', None,
                                          'Gin binding parameters.')
_NETLIST_FILE = flags.DEFINE_string('netlist_file', '',
                                    'File path to the netlist file.')
_INIT_PLACEMENT = flags.DEFINE_string('init_placement', '',
                                      'File path to the init placement file.')
# TODO(b/219085316): Open source dreamplace.
_STD_CELL_PLACER_MODE = flags.DEFINE_string(
    'std_cell_placer_mode', 'fd',
    'Options for fast std cells placement: `fd` (uses the '
    'force-directed algorithm), `dreamplace` (uses DREAMPlace '
    'algorithm).')
_ROOT_DIR = flags.DEFINE_string(
    'root_dir', os.getenv('TEST_UNDECLARED_OUTPUTS_DIR'),
    'Root directory for writing logs/summaries/checkpoints.')
_REPLAY_BUFFER_SERVER_ADDR = flags.DEFINE_string(
    'replay_buffer_server_address', None, 'Replay buffer server address.')
_VARIABLE_CONTAINER_SERVER_ADDR = flags.DEFINE_string(
    'variable_container_server_address', None,
    'Variable container server address.')
_SEQUENCE_LENGTH = flags.DEFINE_integer(
    'sequence_length', 134,
    'The sequence length to estimate shuffle size. Depends on the environment.'
    'Max horizon = T translates to sequence_length T+1 because of the '
    'additional boundary step (last -> first).')
_GLOBAL_SEED = flags.DEFINE_integer(
    'global_seed', 111,
    'Used in env and weight initialization, does not impact action sampling.')

FLAGS = flags.FLAGS


def main(_):
  gin.parse_config_files_and_bindings(
      _GIN_FILE.value, _GIN_BINDINGS.value, skip_unknown=True)

  logging.info('global seed=%d', _GLOBAL_SEED.value)
  np.random.seed(_GLOBAL_SEED.value)
  random.seed(_GLOBAL_SEED.value)
  tf.random.set_seed(_GLOBAL_SEED.value)

  root_dir = os.path.join(_ROOT_DIR.value, str(_GLOBAL_SEED.value))

  strategy = strategy_utils.get_strategy(strategy_utils.TPU.value,
                                         strategy_utils.USE_GPU.value)

  create_env_fn = functools.partial(
      environment.create_circuit_environment,
      netlist_file=_NETLIST_FILE.value,
      init_placement=_INIT_PLACEMENT.value,
      global_seed=_GLOBAL_SEED.value,
      netlist_index=0)

  use_model_tpu = bool(strategy_utils.TPU.value)

  cache = static_feature_cache.StaticFeatureCache()

  env = create_env_fn()
  observation_tensor_spec, action_tensor_spec, time_step_tensor_spec = (
      spec_utils.get_tensor_specs(env))
  static_features = env.wrapped_env().get_static_obs()
  cache.add_static_feature(static_features)

  with strategy.scope():
    actor_net, value_net = model.create_grl_models(
        observation_tensor_spec,
        action_tensor_spec,
        cache.get_all_static_features(),
        use_model_tpu=use_model_tpu,
        seed=_GLOBAL_SEED.value)

  train_ppo_lib.train(
      root_dir=root_dir,
      strategy=strategy,
      replay_buffer_server_address=_REPLAY_BUFFER_SERVER_ADDR.value,
      variable_container_server_address=_VARIABLE_CONTAINER_SERVER_ADDR.value,
      action_tensor_spec=action_tensor_spec,
      time_step_tensor_spec=time_step_tensor_spec,
      sequence_length=_SEQUENCE_LENGTH.value,
      actor_net=actor_net,
      value_net=value_net)


if __name__ == '__main__':
  flags.mark_flags_as_required([
      'root_dir',
      'replay_buffer_server_address',
      'variable_container_server_address',
  ])
  multiprocessing.handle_main(functools.partial(app.run, main))
