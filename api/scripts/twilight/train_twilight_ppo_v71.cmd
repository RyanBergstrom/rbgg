@echo off
cd /d C:\Dev\rbgg\api\scripts
start /B python train_twilight_ppo.py ^
    --timesteps 1000000 ^
    --resume C:\Dev\rbgg\runtime\twilight-ppo-v7.zip ^
    --opponents "rule=0.7,random=0.2,snapshot=0.1" ^
    --learner-faction us ^
    --curriculum manual ^
    --curriculum-stage 2 ^
    --curriculum-min-timesteps 100000 ^
    --max-episode-steps 3000 ^
    --output C:\Dev\rbgg\runtime\twilight-ppo-v71 ^
    --checkpoint-frequency 100000 ^
    --n-envs 4
