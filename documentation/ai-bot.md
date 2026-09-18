# Building a Reusable Board Game AI Engine

## Overview

This document captures the architectural direction for evolving a reusable board game AI engine from a simple Monte Carlo Tree Search (MCTS) implementation into a framework capable of supporting increasingly strategic games.

The immediate pilot game is **Lost Cities**, but the broader goal is to create an engine where individual games plug into a shared AI framework rather than requiring a completely custom AI implementation for every game.

---

# Current Engine Architecture

Current game implementations provide:

```text
Rules Validation
Move Generation
Board State Management
End Game Detection
```

The AI currently:

```text
Calls GetMoves()
Selects moves
Runs MCTS
Builds search trees
Returns best move
```

This works very well for relatively straightforward games such as Checkers.

The next challenge is supporting games where:

```text
Long-term planning exists
Hidden information exists
Probabilities matter
Position quality matters
```

Lost Cities is the first step toward that evolution.

---

# Understanding The Major AI Approaches

## Rule-Based (Utility AI)

The simplest strategic AI.

Each legal move receives a score.

Example:

```text
Play Yellow Investment = 25
Play Yellow 3 = 15
Discard Blue 10 = 4
Discard Yellow 5 = -10
```

The AI simply chooses the highest-scoring move.

### Strengths

```text
Easy to understand
Easy to debug
Fast
Deterministic
```

### Weaknesses

```text
Can be short-sighted
May miss long-term opportunities
Requires handcrafted rules
```

Best for:

```text
Simple games
NPC behavior
Early prototypes
```

---

## Minimax

Minimax explores future decision sequences.

```text
Me
↓
Opponent
↓
Me
↓
Opponent
↓
Evaluate
```

At my turn:

```text
Choose highest score
```

At opponent turn:

```text
Assume opponent chooses lowest score for me
```

Hence:

```text
MINI-MAX
```

### Strengths

```text
Strategic
Predictable
Strong in deterministic games
```

### Weaknesses

```text
Large search trees
Poor fit for hidden information
Complicated by randomness
```

Best for:

```text
Chess
Checkers
Connect Four
Abstract strategy games
```

---

## Alpha-Beta Pruning

Optimization for Minimax.

Example:

```text
Move A already guarantees +20.

Move B can only achieve +10.

Stop searching Move B.
```

Benefits:

```text
Same answer as Minimax
Much faster
```

In practice, Minimax should almost always be paired with Alpha-Beta pruning.

---

## Expectiminimax

Extends Minimax to support randomness.

Tree structure:

```text
MAX
MIN
CHANCE
```

Example:

```text
Player Move
↓
Card Draw
↓
Opponent Move
```

Useful for:

```text
Card games
Dice games
Random events
```

Downside:

```text
Can become extremely expensive
```

---

## Monte Carlo Tree Search (MCTS)

Current engine approach.

Cycle:

```text
Selection
Expansion
Simulation
Backpropagation
```

MCTS discovers good moves through repeated simulations.

### Strengths

```text
Handles large search spaces
Handles uncertainty well
Requires minimal game-specific code
```

### Weaknesses

```text
Random rollouts may play poorly
Can require many simulations
Often lacks strategic understanding
```

Best for:

```text
Complex board games
Card games
Games with hidden information
```

---

## Heuristic-Guided MCTS

Recommended direction for the engine.

```text
MCTS
+
Heuristics
+
Position Evaluation
```

Rather than asking:

```text
Can I finish an entire simulated game?
```

Ask:

```text
How strong is this position after a few future turns?
```

This usually produces much stronger AI while requiring fewer simulations.

---

# Choosing An AI Approach

Every game should be evaluated using several characteristics.

## Hidden Information

Examples:

```text
Lost Cities
Poker
Ticket To Ride
```

Recommended:

```text
MCTS
Heuristic MCTS
```

---

## Randomness

Examples:

```text
Card draws
Dice rolls
Random events
```

Recommended:

```text
MCTS
Expectiminimax
```

---

## Perfect Information

Examples:

```text
Chess
Checkers
Connect Four
```

Recommended:

```text
Minimax
Alpha-Beta
```

---

## Branching Factor

Small:

```text
5-20 moves
```

Minimax becomes more practical.

Large:

```text
50+
100+
```

MCTS becomes more attractive.

---

## Evaluation Difficulty

Easy:

```text
Material count
Position value
```

Minimax works very well.

Hard:

```text
Card synergy
Future potential
Probabilities
```

MCTS generally performs better.

---

# The Role Of Heuristics

A heuristic answers a single question:

```text
How good is this position?
```

The heuristic does NOT predict the future perfectly.

Instead it estimates future value.

---

# Characteristics Of Good Heuristics

Good heuristics measure things humans care about.

Examples:

## Current Strength

```text
Current score
Resources
Territory
Captured pieces
```

## Future Potential

```text
Open expeditions
Card combinations
Resource engines
```

## Flexibility

```text
Number of future options available
```

## Risk

```text
Risk of failure
Risk of committing too early
```

## Opponent Advantage

```text
Does this move help the opponent?
```

## Tempo

```text
Does this move advance my plan?
```

---

# Where Heuristics Should Live

Recommended architecture:

```text
Game Engine
├── Search
├── Tree Management
└── AI Framework

Game
├── Rules
├── State
├── Move Generation
└── Evaluation
```

Suggested interface:

```csharp
interface IGameEvaluator
{
    double EvaluatePosition(GameState state);
}
```

The engine should never understand a game's strategy.

Each game owns its evaluation function.

---

# Recommended Lost Cities Strategy

## Why Pure MCTS Is Not Ideal

Pure MCTS assumes random simulations provide useful information.

In Lost Cities:

```text
Investment cards
Expedition commitment
Card probabilities
Opponent blocking
```

matter greatly.

Random rollouts frequently make terrible decisions.

---

## Recommended Approach

```text
Heuristic Guided MCTS
```

Process:

```text
Selection
↓
Expansion
↓
Simulate 4-8 future turns
↓
EvaluatePosition()
↓
Backpropagate
```

Rather than:

```text
Play entire game to completion
```

---

# Lost Cities Heuristics

## Current Score

Always include actual score.

---

## Expedition Value

Measure potential value of active expeditions.

Example:

```text
Investment
3
4
```

with many remaining yellow cards should score highly.

---

## Expedition Completion Probability

Estimate:

```text
How likely is this expedition to become profitable?
```

---

## Investment Leverage

Investment cards multiply value.

The heuristic should recognize this.

---

## Hand Utility

Measure how useful cards appear.

Example:

```text
3
4
5
```

is usually better than:

```text
10
```

on its own.

---

## Dead Weight

Detect cards that are unlikely to ever be played.

---

## Opponent Opportunity

Estimate value being handed to the opponent.

Example:

```text
Opponent:
Investment
2
3
4

Discard:
5
```

This should generate a penalty.

---

## Flexibility

Reward positions that preserve future options.

---

# Using Heuristics Within MCTS

A common misconception is that heuristics only affect the root move selection.

They can be used throughout the search.

---

## Root Move Evaluation

Before expansion:

```text
Play Yellow Investment = 20
Play Red 6 = 15
Discard Yellow 5 = -10
```

Provides initial guidance.

---

## Move Priors

Nodes can start with an informed prior.

Example:

```text
Play Yellow Investment
Prior = 0.80

Play Red 6
Prior = 0.50

Discard Yellow 5
Prior = 0.05
```

These values influence where search effort is spent.

---

## Heuristic-Guided Rollouts

Instead of:

```text
100% random decisions
```

Use:

```text
80% heuristic choice
20% random choice
```

This preserves discovery while improving rollout quality.

---

## Cutoff Evaluation

Most important heuristic usage.

At cutoff depth:

```text
EvaluatePosition(state)
```

The result becomes the value propagated upward through the tree.

---

# Understanding Simulation Budget

When people say:

```text
Spend simulations
```

They mean:

```text
Which branch receives the next search iteration?
```

The search repeatedly decides:

```text
Where should I explore next?
```

Good-looking branches naturally receive more visits.

Think of simulations as water flowing through a tree.

Heuristics help determine the width of each pipe.

---

# Future Engine Enhancements

## Position Evaluation Framework

Add:

```csharp
interface IGameEvaluator
{
    double EvaluatePosition(GameState state);
}
```

Allows every game to plug into the same search engine.

---

## Move Evaluation Framework

Add:

```csharp
interface IMoveEvaluator
{
    double EvaluateMove(
        GameState state,
        Move move);
}
```

Useful for move ordering and priors.

---

## Multiple Search Strategies

Support:

```text
MCTS
Minimax
Custom
```

through a common abstraction.

Example:

```csharp
interface IGameSearchStrategy
{
    Move FindBestMove(...)
}
```

---

## Chance Nodes

Future-proof support for:

```text
Card draws
Dice
Random events
```

---

## Opponent Modeling

Move from:

```text
Opponent acts randomly
```

to:

```text
Opponent uses its own evaluator
```

inside simulations.

---

## Variable Search Depth

Allow games to determine cutoff depth.

Example:

```text
Lost Cities     6 turns
Checkers       10 turns
Chess           8 turns
```

---

# Long-Term Vision

The most valuable evolution of the engine is likely not replacing MCTS.

Instead:

```text
MCTS
+
Move Evaluation
+
Position Evaluation
+
Heuristic Rollouts
+
Search Cutoffs
```

This preserves the flexibility of MCTS while adding the strategic understanding needed for more sophisticated board games.

Lost Cities is an excellent pilot project because it introduces:

```text
Hidden information
Probability
Long-term planning
Opponent interaction
Position evaluation
```

without introducing an overwhelming ruleset.

Successfully implementing Lost Cities with heuristic-guided MCTS will establish patterns that can be reused across many future board games and will significantly mature the overall engine architecture.
