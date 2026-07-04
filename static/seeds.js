/* Builder seed definitions for every built-in strategy, keyed by strategy
   number. Each seed is a valid no-code builder definition (see
   builder/compiler.py for the closed vocabulary). `approx: true` marks
   strategies whose original logic goes beyond the builder's blocks — the seed
   is a close approximation, not a faithful port. */
const STRATEGY_SEEDS = {
  1: { // Always Coop
    approx: false,
    def: { first_move: "cooperate", rules: [], default_action: { type: "cooperate" } },
  },
  2: { // Always Def
    approx: false,
    def: { first_move: "defect", rules: [], default_action: { type: "defect" } },
  },
  3: { // Tit For Tat
    approx: false,
    def: { first_move: "cooperate", rules: [], default_action: { type: "copy_opponent" } },
  },
  4: { // Grim Trigger
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [{ conditions: [{ fact: "opp_defection_count", op: "gte", value: 1 }], action: { type: "defect" } }],
      default_action: { type: "cooperate" },
    },
  },
  5: { // Pavlov: cooperate iff both made the same move last round
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "my_last_move", op: "is", value: "cooperate" }, { fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "my_last_move", op: "is", value: "defect" }, { fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "cooperate" } },
      ],
      default_action: { type: "defect" },
    },
  },
  6: { // Random (original also randomizes the first move)
    approx: false,
    def: { first_move: "cooperate", rules: [], default_action: { type: "random", p: 0.5 } },
  },
  7: { // Sus Tit For Tat
    approx: false,
    def: { first_move: "defect", rules: [], default_action: { type: "copy_opponent" } },
  },
  8: { // Prober (original locks its verdict after round 3; this re-checks each round)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 2 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "eq", value: 3 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_count", op: "eq", value: 0 }], action: { type: "defect" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  9: { // Tit For Two Tat
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [{ conditions: [{ fact: "opp_defect_streak", op: "gte", value: 2 }], action: { type: "defect" } }],
      default_action: { type: "cooperate" },
    },
  },
  10: { // Anti Tit For Tat
    approx: false,
    def: { first_move: "cooperate", rules: [], default_action: { type: "opposite_of_opponent" } },
  },
  11: { // Hard Tit For Tat (identical to TFT in this arena)
    approx: false,
    def: { first_move: "cooperate", rules: [], default_action: { type: "copy_opponent" } },
  },
  12: { // Random Tit For Tat: 70% copy, 30% defect
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [{ conditions: [{ fact: "chance", op: "lt", value: 0.3 }], action: { type: "defect" } }],
      default_action: { type: "copy_opponent" },
    },
  },
  13: { // Soft Grudger
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [{ conditions: [{ fact: "opp_defection_count", op: "gte", value: 2 }], action: { type: "defect" } }],
      default_action: { type: "cooperate" },
    },
  },
  14: { // Hard Prober (same caveat as Prober)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 2 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "eq", value: 3 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_count", op: "eq", value: 0 }], action: { type: "defect" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  15: { // Joss
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [{ conditions: [{ fact: "chance", op: "lt", value: 0.1 }], action: { type: "defect" } }],
      default_action: { type: "copy_opponent" },
    },
  },
  16: { // Bully
    approx: false,
    def: {
      first_move: "defect",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 2 }, { fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "my_move_n_back", op: "is", value: "defect", n: 2 }, { fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "cooperate" } },
      ],
      default_action: { type: "defect" },
    },
  },
  17: { // Cond Defect
    approx: false,
    def: {
      first_move: "defect",
      rules: [{ conditions: [{ fact: "opp_cooperation_rate", op: "gte", value: 0.5 }], action: { type: "defect" } }],
      default_action: { type: "copy_opponent" },
    },
  },
  18: { // Two Timer (round-parity alternation approximated by flipping own last move)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 2 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defect_streak", op: "gte", value: 2 }], action: { type: "defect" } },
        { conditions: [{ fact: "my_last_move", op: "is", value: "cooperate" }], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  19: { // Appold (original learns response probabilities; approximated with rate tiers)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 4 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "gte", value: 0.8 }], action: { type: "random", p: 0.9 } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "gte", value: 0.5 }], action: { type: "random", p: 0.65 } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "gte", value: 0.2 }], action: { type: "random", p: 0.35 } },
      ],
      default_action: { type: "random", p: 0.1 },
    },
  },
  20: { // Black (original counts defections in last 5 rounds; approximated with overall rate)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 5 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.9 }], action: { type: "random", p: 0.04 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.7 }], action: { type: "random", p: 0.4 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.5 }], action: { type: "random", p: 0.68 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.3 }], action: { type: "random", p: 0.88 } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  21: { // Borufsen (25-round audits and echo detection simplified)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "gte", value: 27 }, { fact: "opp_cooperation_rate", op: "lt", value: 0.3 }], action: { type: "defect" } },
        { conditions: [
          { fact: "opp_defect_streak", op: "gte", value: 3 },
          { fact: "my_last_move", op: "is", value: "defect" },
          { fact: "my_move_n_back", op: "is", value: "defect", n: 2 },
          { fact: "my_move_n_back", op: "is", value: "defect", n: 3 },
        ], action: { type: "cooperate" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  22: { // Cave
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "gt", value: 40 }, { fact: "opp_defection_rate", op: "gt", value: 0.39 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gt", value: 30 }, { fact: "opp_defection_rate", op: "gt", value: 0.65 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gt", value: 20 }, { fact: "opp_defection_rate", op: "gt", value: 0.79 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_count", op: "gte", value: 18 }], action: { type: "defect" } },
      ],
      default_action: { type: "random", p: 0.5 },
    },
  },
  23: { // Champion (final phase's exact punishment odds approximated)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 10 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "round_number", op: "lte", value: 25 }], action: { type: "copy_opponent" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "lt", value: 0.6 }], action: { type: "random", p: 0.5 } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  24: { // Colbert (fixed D,D,C,C punishment script approximated)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 6 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "lte", value: 8 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "defect", n: 2 }], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  25: { // Eatherley (retaliation odds = defection rate, approximated in tiers)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.8 }], action: { type: "random", p: 0.2 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.6 }], action: { type: "random", p: 0.4 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.4 }], action: { type: "random", p: 0.6 } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.2 }], action: { type: "random", p: 0.8 } },
      ],
      default_action: { type: "random", p: 0.95 },
    },
  },
  26: { // Getzler (fading resentment, truncated after four rounds back)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "defect", n: 2 }], action: { type: "random", p: 0.5 } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "defect", n: 3 }], action: { type: "random", p: 0.75 } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "defect", n: 4 }], action: { type: "random", p: 0.875 } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  27: { // Gladstein (drops the one-time apology move)
    approx: true,
    def: {
      first_move: "defect",
      rules: [
        { conditions: [{ fact: "opp_defection_count", op: "gte", value: 1 }], action: { type: "copy_opponent" } },
        { conditions: [{ fact: "my_last_move", op: "is", value: "defect" }], action: { type: "cooperate" } },
      ],
      default_action: { type: "defect" },
    },
  },
  28: { // Graaskamp Katzen (checkpoints re-checked live instead of locking forever)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "gte", value: 11 }, { fact: "my_score", op: "lt", value: 23 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gte", value: 21 }, { fact: "my_score", op: "lt", value: 53 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gte", value: 31 }, { fact: "my_score", op: "lt", value: 83 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gte", value: 41 }, { fact: "my_score", op: "lt", value: 113 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gte", value: 51 }, { fact: "my_score", op: "lt", value: 143 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "gte", value: 101 }, { fact: "my_score", op: "lt", value: 293 }], action: { type: "defect" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  29: { // Grofman (7-round judgment window approximated with overall rate)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 2 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "round_number", op: "lte", value: 7 }], action: { type: "copy_opponent" } },
        { conditions: [{ fact: "my_last_move", op: "is", value: "cooperate" }, { fact: "opp_defection_rate", op: "lte", value: 0.29 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "my_last_move", op: "is", value: "defect" }, { fact: "opp_defection_rate", op: "lte", value: 0.14 }], action: { type: "cooperate" } },
      ],
      default_action: { type: "defect" },
    },
  },
  30: { // Harrington
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "eq", value: 37 }], action: { type: "defect" } },
        { conditions: [{ fact: "round_number", op: "eq", value: 38 }, { fact: "opp_defection_count", op: "lte", value: 1 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defect_streak", op: "gte", value: 20 }], action: { type: "defect" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  31: { // Kluepfel (drops the round-26 randomness audit)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_coop_streak", op: "gte", value: 3 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defect_streak", op: "gte", value: 3 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_coop_streak", op: "eq", value: 2 }], action: { type: "random", p: 0.9 } },
        { conditions: [{ fact: "opp_defect_streak", op: "eq", value: 2 }], action: { type: "random", p: 0.1 } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "random", p: 0.7 } },
      ],
      default_action: { type: "random", p: 0.4 },
    },
  },
  32: { // Leyvraz (exact from round 4 on; tiny deviation in rounds 2-3)
    approx: false,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "cooperate", n: 2 }, { fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [
          { fact: "opp_move_n_back", op: "is", value: "cooperate", n: 3 },
          { fact: "opp_move_n_back", op: "is", value: "defect", n: 2 },
          { fact: "opp_last_move", op: "is", value: "cooperate" },
        ], action: { type: "defect" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "cooperate", n: 3 }, { fact: "opp_move_n_back", op: "is", value: "cooperate", n: 2 }], action: { type: "random", p: 0.5 } },
        { conditions: [{ fact: "opp_move_n_back", op: "is", value: "cooperate", n: 2 }], action: { type: "cooperate" } },
      ],
      default_action: { type: "random", p: 0.25 },
    },
  },
  33: { // Mikkelson (credit account approximated with rates and streaks)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_defect_streak", op: "gte", value: 4 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.4 }], action: { type: "defect" } },
        { conditions: [
          { fact: "round_number", op: "gt", value: 10 },
          { fact: "opp_defection_rate", op: "gte", value: 0.15 },
          { fact: "opp_defect_streak", op: "gte", value: 2 },
        ], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  34: { // Richard Hufford (agreement tracking approximated with cooperation rate)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "mutual_coop_streak", op: "gte", value: 21 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "gt", value: 0.9 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_cooperation_rate", op: "gte", value: 0.625 }], action: { type: "copy_opponent" } },
      ],
      default_action: { type: "defect" },
    },
  },
  35: { // Rowsam (six-round score audits approximated)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.6 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.35 }, { fact: "chance", op: "lt", value: 0.35 }], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  36: { // Tideman Chieruzzi (fresh-start test simplified)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "gte", value: 199 }], action: { type: "defect" } },
        { conditions: [
          { fact: "score_diff", op: "gte", value: 10 },
          { fact: "round_number", op: "gte", value: 21 },
          { fact: "opp_defection_rate", op: "gte", value: 0.8 },
        ], action: { type: "cooperate" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  37: { // Tranquilizer (score regimes approximated)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.4 }], action: { type: "copy_opponent" } },
        { conditions: [{ fact: "mutual_coop_streak", op: "gte", value: 4 }, { fact: "chance", op: "lt", value: 0.2 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }, { fact: "chance", op: "lt", value: 0.35 }], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  38: { // Weiner (odd-block forgiveness and 12-round window approximated)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "opp_defection_count", op: "gte", value: 5 }, { fact: "opp_defection_rate", op: "gte", value: 0.35 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }, { fact: "opp_move_n_back", op: "is", value: "cooperate", n: 2 }], action: { type: "random", p: 0.5 } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
  39: { // White (logarithmic tolerance approximated with a flat rate cap)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 10 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_last_move", op: "is", value: "cooperate" }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_rate", op: "gte", value: 0.25 }], action: { type: "defect" } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  40: { // Wm Adams (halving patience approximated with a fixed probability)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [{ fact: "round_number", op: "lte", value: 2 }], action: { type: "cooperate" } },
        { conditions: [{ fact: "opp_defection_count", op: "eq", value: 4 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_count", op: "eq", value: 7 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_count", op: "eq", value: 9 }], action: { type: "defect" } },
        { conditions: [{ fact: "opp_defection_count", op: "gte", value: 10 }, { fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "random", p: 0.25 } },
      ],
      default_action: { type: "cooperate" },
    },
  },
  41: { // Yamachi (habit prediction approximated by mirroring)
    approx: true,
    def: {
      first_move: "cooperate",
      rules: [
        { conditions: [
          { fact: "round_number", op: "gt", value: 40 },
          { fact: "opp_defection_rate", op: "gt", value: 0.45 },
          { fact: "opp_defection_rate", op: "lt", value: 0.55 },
        ], action: { type: "defect" } },
      ],
      default_action: { type: "copy_opponent" },
    },
  },
};
