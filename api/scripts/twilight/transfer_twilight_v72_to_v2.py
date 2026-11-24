"""Transfer weights from a Schema 1 Twilight Struggle PPO checkpoint (v72) to a Schema 2 model.

Schema 1: 1092 observation features, 781 actions.
Schema 2: 1104 observation features, 894 actions (adds Space Race and CMC cancellation).

The transferred model preserves 100% of the latent representations of v72 for all
legacy features and actions while zero-initializing weights for the 12 new observation
inputs and new action logits.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from sb3_contrib import MaskablePPO

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv


def transfer_v1_to_v2(v1_model_path: str, output_path: str, seed: int = 42) -> None:
    print(f"Loading Schema 1 model from: {v1_model_path}")
    v1_model = MaskablePPO.load(v1_model_path, device="cpu")
    p1 = v1_model.policy

    print("Initializing Schema 2 environment and model...")
    env_v2 = TwilightStruggleGymEnv(seed=seed, schema_version=2)
    v2_model = MaskablePPO(
        "MlpPolicy",
        env_v2,
        seed=seed,
        verbose=1,
        learning_rate=v1_model.learning_rate,
        gamma=v1_model.gamma,
        gae_lambda=v1_model.gae_lambda,
        ent_coef=v1_model.ent_coef,
        policy_kwargs={"net_arch": [512, 512]},
        device="cpu",
    )
    p2 = v2_model.policy

    print("Transferring policy extractor layers...")
    with torch.no_grad():
        # Policy net layer 0: (1104, 512)
        p2.mlp_extractor.policy_net[0].weight.data[:, :1092] = p1.mlp_extractor.policy_net[0].weight.data
        p2.mlp_extractor.policy_net[0].weight.data[:, 1092:] = 0.0
        p2.mlp_extractor.policy_net[0].bias.data.copy_(p1.mlp_extractor.policy_net[0].bias.data)

        # Policy net layer 2: (512, 512)
        p2.mlp_extractor.policy_net[2].weight.data.copy_(p1.mlp_extractor.policy_net[2].weight.data)
        p2.mlp_extractor.policy_net[2].bias.data.copy_(p1.mlp_extractor.policy_net[2].bias.data)

        # Value net layer 0: (1104, 512)
        p2.mlp_extractor.value_net[0].weight.data[:, :1092] = p1.mlp_extractor.value_net[0].weight.data
        p2.mlp_extractor.value_net[0].weight.data[:, 1092:] = 0.0
        p2.mlp_extractor.value_net[0].bias.data.copy_(p1.mlp_extractor.value_net[0].bias.data)

        # Value net layer 2: (512, 512)
        p2.mlp_extractor.value_net[2].weight.data.copy_(p1.mlp_extractor.value_net[2].weight.data)
        p2.mlp_extractor.value_net[2].bias.data.copy_(p1.mlp_extractor.value_net[2].bias.data)

        # Action net: (894, 512)
        p2.action_net.weight.data[:781, :].copy_(p1.action_net.weight.data)
        p2.action_net.weight.data[781:, :] = 0.0
        p2.action_net.bias.data[:781].copy_(p1.action_net.bias.data)
        p2.action_net.bias.data[781:] = 0.0

        # Value net: (1, 512)
        p2.value_net.weight.data.copy_(p1.value_net.weight.data)
        p2.value_net.bias.data.copy_(p1.value_net.bias.data)

    # Carry forward timestep count
    v2_model.num_timesteps = v1_model.num_timesteps

    out_file = Path(output_path)
    if out_file.suffix == ".zip":
        out_save = str(out_file.with_suffix(""))
    else:
        out_save = str(out_file)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    v2_model.save(out_save)
    print(f"Transferred Schema 2 model successfully saved to: {out_save}.zip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-model", default="api/runtime/twilight-ppo-v72.zip",
                        help="Path to Schema 1 source model.")
    parser.add_argument("--output", default="api/runtime/twilight/twilight-ppo-v2-transferred.zip",
                        help="Path to save Schema 2 model.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    transfer_v1_to_v2(args.v1_model, args.output, args.seed)
