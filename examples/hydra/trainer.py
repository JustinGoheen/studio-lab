# Copyright Justin R. Goheen.
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

import os
from pathlib import Path

import hydra
import lightning as L
import torch
from lightning.pytorch import seed_everything
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from lightning.pytorch.loggers import TensorBoardLogger
from lightning.pytorch.profiler import PyTorchProfiler
from omegaconf.dictconfig import DictConfig
from torch.utils.data import TensorDataset

from lightning_pod import conf
from lightning_pod.core.module import LitModel
from lightning_pod.pipeline.datamodule import LitDataModule

# SET PATHS
FILEPATH = Path(__file__)


@hydra.main(
    config_path=str(FILEPATH.parent),
    config_name="trainer",
    version_base=hydra.__version__,
)
def main(cfg: DictConfig) -> None:
    # SET LOGGER
    logger = TensorBoardLogger(conf.LOGSPATH, name="tensorboard")
    # SET PROFILER
    profiler = PyTorchProfiler(dirpath=conf.PROFILERPATH, filename="profiler")
    # SET CHECKPOINT CALLBACK
    checkpoint_callback = ModelCheckpoint(dirpath=conf.CHKPTSPATH, filename="model")
    # SET EARLYSTOPPING CALLBACK
    early_stopping = EarlyStopping(monitor="loss", mode="min")
    # SET CALLBACKS
    callbacks = [checkpoint_callback, early_stopping]
    # SET PLUGINS
    plugins = None
    # SET SEED
    seed_everything(conf.GLOBALSEED, workers=True)
    #  SET DATALOADER
    datamodule = LitDataModule()
    #  SET MODEL
    model = LitModel()
    # SET TRAINER
    trainer = L.Trainer(logger=logger, profiler=profiler, callbacks=callbacks, plugins=plugins, **cfg.trainer)
    # TRAIN MODEL
    trainer.fit(model=model, datamodule=datamodule)
    # IF NOT FAST DEV RUN: TEST, PREDICT, PERSIST
    if not cfg.trainer.fast_dev_run:
        # TEST MODEL
        trainer.test(ckpt_path="best", datamodule=datamodule)
        # PERSIST MODEL
        # TODO write util to search models dir and append version number
        input_sample = datamodule.train_data.dataset[0][0]
        model.to_onnx(conf.MODELPATH, input_sample=input_sample, export_params=True)
        # PREDICT
        predictions = trainer.predict(model, datamodule.val_dataloader())
        # EXPORT PREDICTIONS
        predictions = torch.vstack(predictions)  # type: ignore[arg-type]
        predictions = TensorDataset(predictions)
        torch.save(predictions, conf.PREDSPATH)
        # EXPORT ALL DATA SPLITS FOR REPRODUCIBILITY
        train_split_fname = os.path.join(conf.SPLITSPATH, "train.pt")
        test_split_fname = os.path.join(conf.SPLITSPATH, "test.pt")
        val_split_fname = os.path.join(conf.SPLITSPATH, "val.pt")
        torch.save(datamodule.train_data, train_split_fname)
        torch.save(datamodule.test_data, test_split_fname)
        torch.save(datamodule.val_data, val_split_fname)


if __name__ == "__main__":
    main()
