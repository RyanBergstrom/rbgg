"""Count and time deepcopy calls made from engine code while replaying recorded games."""
import collections
import copy
import sys
import time

sys.path.insert(0, ".")
from app.games.twilight_struggle.validator import TwilightStruggleValidator
from tests.helpers_twilight_replay import initial_state, load_traces

calls = collections.Counter()
seconds = collections.Counter()
depth = [0]
real_deepcopy = copy.deepcopy


def counting_deepcopy(obj, memo=None, _nil=[]):
    if depth[0] > 0:
        return real_deepcopy(obj, memo)
    frame = sys._getframe(1)
    where = f"{frame.f_code.co_filename.split('twilight_struggle')[-1].split('core')[-1]}:{frame.f_code.co_name}"
    depth[0] += 1
    start = time.perf_counter()
    try:
        return real_deepcopy(obj, memo)
    finally:
        seconds[where] += time.perf_counter() - start
        calls[where] += 1
        depth[0] -= 1


import importlib
for name in ("validator", "events", "actions", "action_rounds", "operations", "headlines", "lifecycle", "scoring", "turns"):
    module = importlib.import_module(f"app.games.twilight_struggle.{name}")
    if hasattr(module, "deepcopy"):
        module.deepcopy = counting_deepcopy

validator = TwilightStruggleValidator()
traces = load_traces()[:6]
moves = 0
start = time.perf_counter()
for trace in traces:
    state = initial_state(validator, trace["seed"])
    for move in trace["moves"]:
        validator.validate_move(state, move)
        state = validator.apply_move(state, move)
        moves += 1
total = time.perf_counter() - start

print(f"moves={moves} total={total:.2f}s per_move={total/moves*1000:.1f}ms")
print(f"copies per move = {sum(calls.values())/moves:.1f}; copy time = {sum(seconds.values()):.2f}s ({sum(seconds.values())/total*100:.0f}% of total)")
for where, count in calls.most_common(14):
    print(f"{count/moves:6.2f}/move  {seconds[where]:6.2f}s  {where}")
