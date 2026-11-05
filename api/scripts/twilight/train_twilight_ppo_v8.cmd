@echo off
cd /d C:\Dev\rbgg\api\scripts\twilight
start /B python train_twilight_static_ppo.py ^
    --timesteps 1000000 ^
    --resume C:\Dev\rbgg\api\runtime\twilight\twilight-ppo-v72.zip ^
    --static-opponent C:\Dev\rbgg\api\runtime\twilight\twilight-ppo-v7.zip ^
    --learner-faction us ^
    --curriculum-stage 2 ^
    --max-episode-steps 3000 ^
    --output C:\Dev\rbgg\api\runtime\twilight\twilight-ppo-v8 ^
    --checkpoint-frequency 100000 ^
    --n-envs 4
