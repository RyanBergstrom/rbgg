"""Quick test to verify Twilight Struggle env works."""
from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv

env = TwilightStruggleGymEnv(seed=42, opponents={"rule": 1.0}, curriculum_stage=0)
obs, info = env.reset(seed=12345)
print("Reset OK, obs shape:", obs.shape)
print("Info:", info)

# Quick step
legal = [i for i, f in enumerate(env.action_masks()) if f]
print("Legal moves count:", len(legal))
if legal:
    obs2, reward, terminated, truncated, info2 = env.step(legal[0])
    print("Step OK, reward:", reward, "term:", terminated, "trunc:", truncated)

env.close()
print("Test passed!")