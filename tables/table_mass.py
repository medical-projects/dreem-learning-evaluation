from evaluation import ResultsEvaluation, evaluation_bis
from sklearn.metrics import accuracy_score, f1_score, cohen_kappa_score, balanced_accuracy_score
import pandas as pd
import os

if __name__ == "__main__":
    dataset = "mass"
    table = "base_models"
    results_folder = f"./results/{dataset}/{table + '/' if table is not None else ''}"
    consensus_folder = "./consensus/{}/".format(dataset)

    records = [x.replace(".json", "") for x in os.listdir(consensus_folder)]
    records.sort()

    def f1_macro(x, y):
        return f1_score(x, y, average="macro", labels=[0, 1, 2, 3, 4])

    results = {}
    for metric in [f1_macro, balanced_accuracy_score, accuracy_score, cohen_kappa_score]:

        results[metric.__name__] = evaluation_bis(results_folder, consensus_folder, metric)
    df = pd.DataFrame(results)
    df = df.iloc[[i for i, x in enumerate(df.index) if "std" not in x]]
    df = df.sort_values("f1_macro", ascending=False)
    print(df[["f1_macro"]])
