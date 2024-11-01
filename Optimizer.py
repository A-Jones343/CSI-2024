from Reader import Reader, Available
from Roll_Inventory_Optimizer_Scoring import officialScorer
import pandas as pd

Week = "2024-09-06 Week 1"

Machine = Reader(Week)
Available = Available(Week)
totalScore, scoringBreakdown = officialScorer(Week, False, False, False, False)

print(pd.Series(scoringBreakdown))
