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

from typing import Optional

import lightning as L
import torch.nn.functional as F
from torch import nn, optim
from torchmetrics.functional import accuracy, structural_similarity_index_measure


class Encoder(nn.Module):
    """an encoder layer

    Args:
        dropout: float = probability of an element to be zeroed. Default: 0.5

    Returns:
        an encoded image.

    Note:
        PodModule was initially based on examples found in Lightning docs, and was adapted to account for
        the Optuna Trial.
        The encoder flow is as follows: Sequential(Linear, PReLU, Dropout, Linear).

        - for Sequential containers see
        https://pytorch.org/docs/stable/generated/torch.nn.Sequential.html#torch.nn.Sequential
        - for Linear see
        https://pytorch.org/docs/stable/generated/torch.nn.Linear.html?highlight=linear#torch.nn.Linear
        - for PReLU see
        https://pytorch.org/docs/stable/generated/torch.nn.PReLU.html?highlight=prelu#torch.nn.PReLU
        - for Dropout see
        https://pytorch.org/docs/stable/generated/torch.nn.Dropout.html
    """

    def __init__(self, dropout: float = 0.5):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(
                in_features=28 * 28,
                out_features=64,
                bias=True,
            ),
            nn.PReLU(
                inplace=False,
            ),
            nn.Dropout(dropout),
            nn.Linear(
                in_features=64,
                out_features=3,
                bias=True,
            ),
        )

    def forward(self, x):
        return self.encoder(x)


class Decoder(nn.Module):
    """a decoder layer

    Args:
        dropout: float = probability of an element to be zeroed. Default: 0.5

    Returns:
        a decoded image.

    Note:
        PodModule was initially based on examples found in Lightning docs, and was adapted to
        account for the Optuna Trial.
        The decoder flow is as follows: Sequential(Linear, PReLU, Linear).

        - for Sequential containers see
        https://pytorch.org/docs/stable/generated/torch.nn.Sequential.html#torch.nn.Sequential
        - for Linear see
        https://pytorch.org/docs/stable/generated/torch.nn.Linear.html?highlight=linear#torch.nn.Linear
        - for PReLU see
        https://pytorch.org/docs/stable/generated/torch.nn.PReLU.html?highlight=prelu#torch.nn.PReLU
    """

    def __init__(self, dropout: float = 0.5):
        super().__init__()
        self.decoder = nn.Sequential(
            nn.Linear(
                in_features=3,
                out_features=64,
                bias=True,
            ),
            nn.PReLU(
                inplace=False,
            ),
            nn.Dropout(dropout),
            nn.Linear(
                in_features=64,
                out_features=28 * 28,
                bias=True,
            ),
        )

    def forward(self, x):
        logits = self.decoder(x)
        return logits


class PodModule(L.LightningModule):
    """a custom PyTorch Lightning LightningModule

    Note:
        PodModule was initially based on examples found in Lightning docs, and was adapted to account
        for the Optuna Trial.
        The flow is as follows:
        [encoder: Sequential(Linear, PReLU, Dropout, Linear), decoder: Sequential(Linear, PReLU, Linear)].

        - for Sequential containers see
        https://pytorch.org/docs/stable/generated/torch.nn.Sequential.html#torch.nn.Sequential
        - for Linear see https://pytorch.org/docs/stable/generated/torch.nn.Linear.html?highlight=linear#torch.nn.Linear
        - for PReLU see https://pytorch.org/docs/stable/generated/torch.nn.PReLU.html?highlight=prelu#torch.nn.PReLU
        - for Dropout see https://pytorch.org/docs/stable/generated/torch.nn.Dropout.html
    """

    def __init__(
        self,
        optimizer: Optional[optim.Optimizer] = optim.Adam,
        lr: float = 1e-3,
        dropout: float = 0.5,
        accuracy_task: str = "multilabel",
    ):
        super().__init__()
        self.encoder = Encoder(dropout)
        self.decoder = Decoder(dropout)
        self.optimizer = optimizer
        self.lr = lr
        self.accuracy_task = accuracy_task
        self.save_hyperparameters()

    def forward(self, x):
        x = x.view(x.size(0), -1)
        z = self.encoder(x)
        x_hat = self.decoder(z)
        y_hat = F.log_softmax(x_hat, dim=1)
        return x_hat, y_hat

    def training_step(self, batch):
        self._common_flow(batch, "training")

    def test_step(self, batch, *args):
        self._common_flow(batch, "test")

    def validation_step(self, batch, *args):
        self._common_flow(batch, "val")

    def _common_flow(self, batch, stage):
        """
        Note:
            For more on SSIM, see: https://torchmetrics.readthedocs.io/en/stable/image/structural_similarity.html
        """
        x, y = batch
        x = x.view(x.size(0), -1)
        z = self.encoder(x)
        x_hat = self.decoder(z)
        y_hat = F.log_softmax(x_hat, dim=1)
        loss = F.mse_loss(x_hat, x)

        if stage in ["val", "test"]:
            acc = accuracy(y_hat, y, accuracy_task=self.accuracy_task)
            ssim = structural_similarity_index_measure(x_hat, x)
            self.log(f"{stage}_ssim ", ssim)
            self.log(f"{stage}_acc", acc)
            self.log(f"{stage}_loss", loss)
        if stage == "training":
            self.log(f"{stage}_loss", loss)
            return loss

    def predict_step(self, batch, batch_idx, dataloader_idx=0):
        x, y = batch
        return self(x)

    def configure_optimizers(self):
        optimizer = self.optimizer(self.parameters(), lr=self.lr)
        return optimizer
