"""Pure, side-effect-free Rami Portugais rules engine.

No I/O, no sockets, no wall-clock, no global randomness: every function takes
its inputs explicitly (the shuffle takes an injected `random.Random`). This is
what makes the whole rulebook exhaustively unit-testable.
"""
