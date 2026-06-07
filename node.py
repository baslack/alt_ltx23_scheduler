import math

import torch
from typing_extensions import override

from comfy_api.latest import ComfyExtension, io


class LTXVSchedulerPower(io.ComfyNode):
    """A variation on the stock LTXVScheduler that exposes the ``power`` exponent.

    The stock node hardcodes ``power = 1``, which makes the sigma curve a plain
    logistic: holding nearer to 1 (higher shift) necessarily flattens the slope
    at the midpoint and pushes the whole descent into the final steps. ``power``
    multiplies the midpoint slope without changing the midpoint value, so you can
    keep a high hold *and* drop out of the midpoint faster for a more even
    descent. Values around 1.5-2.0 are a good starting range.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LTXVSchedulerPower",
            display_name="LTXVScheduler (Power)",
            category="model/sampling/schedulers",
            inputs=[
                io.Int.Input("steps", default=20, min=1, max=10000),
                io.Float.Input("max_shift", default=2.05, min=0.0, max=100.0, step=0.01),
                io.Float.Input("base_shift", default=0.95, min=0.0, max=100.0, step=0.01),
                io.Float.Input(
                    id="power",
                    default=1.0,
                    min=0.1,
                    max=10.0,
                    step=0.01,
                    tooltip="Exponent on the (1/sigma - 1) term. 1.0 matches the "
                    "stock node. Higher values steepen the slope at the midpoint "
                    "without changing the value there, for a more even descent.",
                ),
                io.Boolean.Input(
                    id="stretch",
                    default=True,
                    tooltip="Stretch the sigmas to be in the range [terminal, 1].",
                    advanced=True,
                ),
                io.Float.Input(
                    id="terminal",
                    default=0.1,
                    min=0.0,
                    max=0.99,
                    step=0.01,
                    tooltip="The terminal value of the sigmas after stretching.",
                    advanced=True,
                ),
                io.Latent.Input("latent", optional=True),
            ],
            outputs=[
                io.Sigmas.Output(),
            ],
        )

    @classmethod
    def execute(cls, steps, max_shift, base_shift, power, stretch, terminal, latent=None) -> io.NodeOutput:
        if latent is None:
            tokens = 4096
        else:
            tokens = math.prod(latent["samples"].shape[2:])

        sigmas = torch.linspace(1.0, 0.0, steps + 1)

        x1 = 1024
        x2 = 4096
        mm = (max_shift - base_shift) / (x2 - x1)
        b = base_shift - mm * x1
        sigma_shift = (tokens) * mm + b

        sigmas = torch.where(
            sigmas != 0,
            math.exp(sigma_shift) / (math.exp(sigma_shift) + (1 / sigmas - 1) ** power),
            0,
        )

        # Stretch sigmas so that its final value matches the given terminal value.
        if stretch:
            non_zero_mask = sigmas != 0
            non_zero_sigmas = sigmas[non_zero_mask]
            one_minus_z = 1.0 - non_zero_sigmas
            scale_factor = one_minus_z[-1] / (1.0 - terminal)
            stretched = 1.0 - (one_minus_z / scale_factor)
            sigmas[non_zero_mask] = stretched

        return io.NodeOutput(sigmas)


class AltLtx23SchedulerExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            LTXVSchedulerPower,
        ]


async def comfy_entrypoint() -> AltLtx23SchedulerExtension:
    return AltLtx23SchedulerExtension()
