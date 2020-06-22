import json
import os
from collections import OrderedDict
from functools import partial

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, f1_score
from tabulate import tabulate


def compute_soft_agreement(hypnogram, hypnograms_consensus):
    epochs = range(len(hypnogram))
    probabilistic_consensus = np.zeros((6, len(hypnogram)))
    for hypnogram_consensus in hypnograms_consensus:
        probabilistic_consensus[np.array(hypnogram_consensus) + 1, range(len(hypnogram))] += 1
    probabilistic_consensus_normalized = probabilistic_consensus / probabilistic_consensus.max(0)
    soft_agreement = probabilistic_consensus_normalized[np.array(hypnogram) + 1, epochs].mean()
    return soft_agreement


def build_consensus_hypnogram(ranked_hypnograms_consensus):
    """In this function order matters, first hypnogram is the reference in case of ties"""
    number_of_epochs = len(ranked_hypnograms_consensus[0])
    probabilistic_consensus = np.zeros((6, number_of_epochs))
    ranked_hypnograms_consensus_array = np.array(ranked_hypnograms_consensus) + 1
    for hypnogram_consensus in ranked_hypnograms_consensus_array:
        probabilistic_consensus[np.array(hypnogram_consensus), range(number_of_epochs)] += 1

    consensus_hypnogram = np.argmax(probabilistic_consensus, 0)
    ties = (
                   probabilistic_consensus ==
                   probabilistic_consensus[consensus_hypnogram, range(number_of_epochs)]
           ).sum(0) > 1
    consensus_hypnogram[ties] = np.array(ranked_hypnograms_consensus_array[0])[ties]
    consensus_probability = (probabilistic_consensus[consensus_hypnogram, range(number_of_epochs)] /
                             len(ranked_hypnograms_consensus_array))
    consensus_hypnogram = consensus_hypnogram - 1
    return consensus_hypnogram, consensus_probability


def get_cohen_kappa(hypnogram, consensus, stage=None):
    consensus_hypnogram, consensus_probability = consensus
    mask = (consensus_hypnogram != -1)
    y1 = consensus_hypnogram[mask]
    y2 = hypnogram[mask]
    if stage is not None:
        y1 = y1 == stage
        y2 = y2 == stage
    score = cohen_kappa_score(y1, y2, sample_weight=consensus_probability[mask])
    return score


def get_f1_score(hypnogram, consensus, stage=None):
    consensus_hypnogram, consensus_probability = consensus
    mask = (consensus_hypnogram != -1)
    if stage is None:
        score = f1_score(
            consensus_hypnogram[mask],
            hypnogram[mask],
            labels=[0, 1, 2, 3, 4],
            average="weighted",
            sample_weight=consensus_probability[mask]
        )
    else:
        score = f1_score(
            consensus_hypnogram[mask],
            hypnogram[mask],
            labels=[0, 1, 2, 3, 4],
            average=None,
            sample_weight=consensus_probability[mask]
        )[stage]
    return score


def get_accuracy_score(hypnogram, consensus, stage=None):
    consensus_hypnogram, consensus_probability = consensus
    if stage is not None:
        mask = (consensus_hypnogram == stage)
    else:
        mask = (consensus_hypnogram != -1)
    y1 = consensus_hypnogram[mask]
    y2 = hypnogram[mask]
    p = consensus_probability[mask]

    score = ((y1 == y2) * p).sum() / p.sum()
    return score


get_metrics = OrderedDict({
    "f1_score": get_f1_score,
    "accuracy_score": get_accuracy_score,
    "cohen_kappa": get_cohen_kappa,
    "f1_score_0": partial(get_f1_score, stage=0),
    "accuracy_score_0": partial(get_accuracy_score, stage=0),
    "cohen_kappa_0": partial(get_cohen_kappa, stage=0),
    "f1_score_1": partial(get_f1_score, stage=1),
    "accuracy_score_1": partial(get_accuracy_score, stage=1),
    "cohen_kappa_1": partial(get_cohen_kappa, stage=1),
    "f1_score_2": partial(get_f1_score, stage=2),
    "accuracy_score_2": partial(get_accuracy_score, stage=2),
    "cohen_kappa_2": partial(get_cohen_kappa, stage=2),
    "f1_score_3": partial(get_f1_score, stage=3),
    "accuracy_score_3": partial(get_accuracy_score, stage=3),
    "cohen_kappa_3": partial(get_cohen_kappa, stage=3),
    "f1_score_4": partial(get_f1_score, stage=4),
    "accuracy_score_4": partial(get_accuracy_score, stage=4),
    "cohen_kappa_4": partial(get_cohen_kappa, stage=4),
})


class ResultsEvaluation:

    def __init__(self,
                 scorers_folder,
                 results_folder=None,
                 record_blacklist=[],
                 lights_off={},
                 lights_on={},
                 start_times=None):
        # Retrieve scorers
        self.scorers = os.listdir(scorers_folder)
        self.index = {}
        self.scorers_folder = {
            scorer: f'{scorers_folder}{scorer}/'
            for scorer in self.scorers
        }
        # Intersection of all available scored records
        self.records = sorted(list(set.intersection(*(
            {record.split(".json")[0] for record in os.listdir(self.scorers_folder[scorer]) if
             record.split(".json")[0] not in record_blacklist}
            for scorer in self.scorers
        ))))
        print(f"Found {len(self.records)} records and {len(self.scorers)} scorers.")

        # Retrieve scorer hypnograms
        self.scorer_hypnograms = {
            scorer: {
                record: np.array(
                    json.load(open(f"{self.scorers_folder[scorer]}/{record}.json", "r")))
                for record in self.records
            }
            for scorer in self.scorers
        }
        self.hypnogram_sizes = {}
        for record in self.records:
            hypnogram_size = set([
                len(self.scorer_hypnograms[scorer][record]) for scorer in self.scorers
            ])
            assert len(hypnogram_size) == 1
            self.hypnogram_sizes[record] = hypnogram_size.pop()

        # Retrieve results hypnograms
        if results_folder is not None:
            self.results = os.listdir(results_folder)
        else:
            self.results = []

        self.results_folder = {
            result: f'{results_folder}{result}/'
            for result in self.results
            if sorted([record.split(".json")[0]
                       for record in os.listdir(f'{results_folder}/{result}/') if
                       record.split(".json")[0] not in record_blacklist
                       if record[-5:] == ".json"]) == self.records
        }

        self.result_hypnograms = {
            result: {
                record: np.array(
                    json.load(open(f"{self.results_folder[result]}/{record}.json", "r")))
                for record in self.records
            }
            for result in self.results
        }

        # Cut hypnograms to light on and off
        for record in self.records:
            # if results hypnogram length is the same as scorer hypno, we have to truncate it

            hypnograms = [self.scorer_hypnograms[scorer][record] for scorer in self.scorers]
            index_min = max([np.where(np.array(hypnogram) >= 0)[0][0]
                             for hypnogram in hypnograms])
            index_min = max(index_min, lights_off.get(record, 0))
            index_max = (len(hypnograms[0]) - max([np.where(np.array(hypnogram)[::-1] >= 0)[0][0]
                                                   for hypnogram in hypnograms]))
            index_max = min(index_max, lights_on.get(record, np.inf))
            self.index[record] = index_min, index_max
            for result in self.results:

                if len(self.result_hypnograms[result][record]) == self.hypnogram_sizes[record]:
                    self.result_hypnograms[result][record] = self.result_hypnograms[result][record][
                                                             index_min:index_max]
            for scorer in self.scorers:
                # removes light on, off and update hypnograll size accordingly
                self.scorer_hypnograms[scorer][record] = self.scorer_hypnograms[scorer][record][
                                                         index_min:index_max]
                self.hypnogram_sizes[record] += index_max - self.hypnogram_sizes[record] - index_min

        # check that the length are ok
        for result in self.result_hypnograms.keys():
            for record in self.records:
                assert len(self.result_hypnograms[result][record]) == self.hypnogram_sizes[record]

        # Build up scorer ranking
        self.scorers_ranking = {
            record: sorted(
                self.scorers,
                key=lambda scorer: -compute_soft_agreement(
                    self.scorer_hypnograms[scorer][record],
                    [self.scorer_hypnograms[other_scorer][record]
                     for other_scorer in self.scorers if other_scorer != scorer],
                )
            )
            for record in self.records
        }
        self.scorers_soft_agreement = [
            (scorer,
             np.mean([
                 compute_soft_agreement(
                     self.scorer_hypnograms[scorer][record],
                     [self.scorer_hypnograms[other_scorer][record]
                      for other_scorer in self.scorers if other_scorer != scorer]
                 ) for record in self.records
             ]))
            for scorer in sorted(self.scorers)
        ]

        # Build consensus hypnogram for scorers
        self.scorer_hypnograms_consensus = {
            scorer: {
                record: build_consensus_hypnogram(
                    [self.scorer_hypnograms[other_scorer][record] for other_scorer in
                     self.scorers_ranking[record]
                     if other_scorer != scorer]
                )
                for record in self.records
            }
            for scorer in self.scorers
        }

        # Metrics for scorers
        self.metrics = {}
        self.raw_metrics = {}
        for scorer in self.scorers:
            self.metrics[scorer] = {}
            self.raw_metrics[scorer] = {}
            for metric_name, get_metric in get_metrics.items():
                values = [
                    get_metric(
                        self.scorer_hypnograms[scorer][record],
                        self.scorer_hypnograms_consensus[scorer][record],
                    ) for record in self.records
                ]
                self.raw_metrics[scorer][metric_name] = values
                self.metrics[scorer][metric_name] = (np.nanmean(values), np.nanstd(values))

        # Metrics for overall scorers
        self.metrics["Overall Scorers"] = {}
        for metric_name, get_metric in get_metrics.items():
            values = [
                get_metric(
                    self.scorer_hypnograms[scorer][record],
                    self.scorer_hypnograms_consensus[scorer][record],
                ) for record in self.records for scorer in self.scorers
            ]
            self.metrics["Overall Scorers"][metric_name] = (np.nanmean(values), np.nanstd(values))

        # Metrics for results
        self.result_hypnograms_consensus = {
            record: build_consensus_hypnogram(
                [self.scorer_hypnograms[scorer][record]
                 for scorer in self.scorers_ranking[record][:-1]]  # N - 1 scorings
            )
            for record in self.records
        }

        for result in self.results:
            self.metrics[result] = {}
            self.raw_metrics[result] = {}
            for metric_name, get_metric in get_metrics.items():
                values = [
                    get_metric(
                        self.result_hypnograms[result][record],
                        self.result_hypnograms_consensus[record],
                    ) for record in self.records
                ]
                self.raw_metrics[result][metric_name] = values
                self.metrics[result][metric_name] = (np.nanmean(values), np.nanstd(values))

    def print_soft_agreements(self):
        print(
            tabulate(
                self.scorers_soft_agreement,
                headers=["Scorer", "SoftAgreement"],
                tablefmt="fancy_grid"
            )
        )

    def print_scores(self):
        keys = self.results + ["Overall Scorers"] + sorted(self.scorers)
        print(
            tabulate(
                [
                    [metric_key] + [
                        (f"{round(self.metrics[key][metric_key][0] * 100, 1)} ± "
                         f"{round(self.metrics[key][metric_key][1] * 100, 1)}")
                        for key in keys]
                    for metric_key in get_metrics.keys()
                ],
                headers=keys,
                tablefmt="fancy_grid"
            )
        )

    def return_scores(self):
        keys = self.results + ["Overall Scorers"] + sorted(self.scorers)
        return tabulate(
            [
                [metric_key] + [
                    (f"{round(self.metrics[key][metric_key][0] * 100, 1)} ± "
                     f"{round(self.metrics[key][metric_key][1] * 100, 1)}")
                    for key in keys]
                for metric_key in get_metrics.keys()
            ],
            headers=keys,
            tablefmt="latex_raw"
        )

    def compute_pairwise_comparison(self, metric='kappa_score'):
        from scipy.stats import mannwhitneyu
        result = np.zeros(shape=(len(self.raw_metrics), len(self.raw_metrics)))
        for i, model_a in enumerate(self.raw_metrics):
            x_a = np.array(self.raw_metrics[model_a][metric])
            for j, model_b in enumerate(self.raw_metrics):
                x_b = np.array(self.raw_metrics[model_b][metric])
                result[i, j] = mannwhitneyu(x_a, x_b)[1]
        df = pd.DataFrame(data=result)
        df.index = (list(self.raw_metrics.keys()))
        df.columns = list(self.raw_metrics.keys())
        return df

    def get_confusion_matrix(self):
        from sklearn.metrics import confusion_matrix
        models_confusion_matrices = {}
        scorers_confusion_matrices = {}
        consensus_hypnogram = np.concatenate(
            [hypno[0] for record, hypno in self.result_hypnograms_consensus.items()]).reshape(-1)
        for model in self.result_hypnograms:
            model_hypnogram = np.concatenate(
                [hypno for record, hypno in self.result_hypnograms[model].items()]).reshape(-1)
            models_confusion_matrices[model] = confusion_matrix(consensus_hypnogram,
                                                                model_hypnogram,
                                                                labels=[0, 1, 2, 3, 4])
        for scorer in self.scorer_hypnograms:
            scorer_hypnogram = np.concatenate(
                [hypno for record, hypno in self.scorer_hypnograms[scorer].items()]).reshape(-1)
            scorers_confusion_matrices[scorer] = confusion_matrix(consensus_hypnogram,
                                                                  scorer_hypnogram,
                                                                  labels=[0, 1, 2, 3, 4])
        return scorers_confusion_matrices, models_confusion_matrices


def evaluation_bis(models_folder, scorer_folder, metric=f1_score, records=None, blacklist=None):
    if records is None:
        records = [x.replace(".json", "") for x in os.listdir(scorer_folder)]
    if blacklist is not None:
        records = [x for x in records if x not in blacklist]
    results = {}
    for model in os.listdir(models_folder):
        model_folder = f"{models_folder}/{model}/"
        hypno_model, hypno_true = {}, {}
        for record in records:
            hypno_model[record] = json.load(open(f"{model_folder}/{record}.json"))
            hypno_true[record] = json.load(open(f"{scorer_folder}/{record}.json"))
        values = []
        for reps in range(1):
            y_model, y_scorer = [], []
            for record in records:
                if np.random.uniform() < 1:
                    try:
                        _y_model = hypno_model[record]
                        _y_scorer = hypno_true[record]
                        assert len(_y_model) == len(_y_scorer), record
                        y_model += _y_model
                        y_scorer += _y_scorer
                    except FileNotFoundError:
                        pass

            y_model = np.array(y_model)
            y_scorer = np.array(y_scorer)
            y_model, y_scorer = y_model[y_scorer >= 0], y_scorer[y_scorer >= 0]
            values += [metric(y_scorer, y_model)]
        results[model] = np.mean(values)
        results[model + "_std"] = np.percentile(values, 2.5), np.percentile(values, 97.5)
    return results
