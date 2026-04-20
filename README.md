# Prisoner’s Dilemma Simulator
This project exists to answer one question:

> *Under realistic conditions (noise, exploitation, limited interaction), which forms of cooperation actually survive?*

## Overview

This project implements and explores **Iterated Prisoner’s Dilemma tournaments** inspired by Robert Axelrod’s work, with a focus on:

- Implementing strategies
- Visualizing the tournament results in the form of a racing bar chart
- Implementing noise
- Implementing evolution over time
- Visualizing evolution over time in the form of a graph

---

## Core Ideas

- Strategies are implemented as **pure functions**:
  - Input: match history
  - Output: `True` (cooperate) or `False` (defect)
- Tournaments are run in a **round-robin** fashion
- Payoffs follow the classical Prisoner’s Dilemma matrix
- Noise is introduced as **misinterpretation of opponent actions**
- Results are analyzed and visualized independently from simulation logic

---

## Project Structure
```
Prisoners_dilemma/
|
├── axelrod_lib/        # enabling use of axelrod strategies in our code
│
├── core/               # Core mechanics (match history, scoring)
│
├── strategies/         # Individual strategy implementations
│   ├── s01_*.py
│   ├── s02_*.py
│   └── ...
|
├── outputs/            # Outputs of the racing bar charts
│
├── simulation/         # Round robin tournaments, aggregations
│
├── interaction/        # (Planned) interaction filtering / persistence
│
├── evolution/          # Population dynamics over time
│
├── metrics/            # Score aggregation, rankings
│
└── visualization/      # Plots, racing bar charts

````

Each layer has a **single responsibility**:
- `simulation` produces data
- `visualization` consumes data
- strategies are isolated and interchangeable

---

## Strategies

The project includes a growing set of strategies inspired by Axelrod’s tournament, including:

### Cooperative / Reciprocal
- Always Cooperate
- Tit for Tat
- Generous Tit for Tat
- Suspicious Tit for Tat

### Retaliatory
- Grim Trigger
- Hard / Soft Grudger
- Delayed Grim

### Adaptive
- Win–Stay Lose–Shift (Pavlov)
- Conditional strategies based on opponent behavior

### Exploitative
- Opportunists
- Probers
- Bullies
- Noise-exploiting strategies

---

## Noise Model

Noise is implemented as a **probability of misperception**:
- A strategy may observe the opponent’s action incorrectly
- This directly impacts:
  - Retaliation
  - Forgiveness
  - Long-term cooperation stability

Noise can be tuned globally to explore robustness and collapse.

---

## Simulation Output

Simulations produce:
- Full match histories
- Cumulative scores per strategy over time
- Rankings at each round

---

## Visualization

The project uses:
- Static plots (scores, rankings)
- **Racing bar charts** to visualize dominance shifts over time

Visualization code is fully decoupled from simulation logic.

---

## Requirements

- Python 3.10+
- pandas
- matplotlib
- bar_chart_race
- axelrod

---

## Implementations

After installing all the necessary libraries, to run the code, run the command ```python -m folder_name/python_file```
like so ```python -m visualization.data_rbc```

### New CLI entrypoint

Use the dedicated CLI wrapper:

`python -m cli --list-strategies`

`python -m cli --strategies "s01 - Always Coop" "s03 - Tit For Tat" --rounds 200 --iterations 5 --noise 0.05`

### New web interface

Install web dependencies:

`pip install -r requirements.txt`

Run API server:

`uvicorn api:app --reload`

Open:

`http://127.0.0.1:8000`

