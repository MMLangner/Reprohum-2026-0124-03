

import pandas as pd
from random import shuffle
import numpy as np

num_lists = 6
num_trials_per_list = 24


# first in each list extracted from the original php files, remaining order is unknown

start_trials = {
    1:20063,
    2:18940,
    3:18844,
    4:18940,
    5:20207,
    6:19273
}

trial_df = pd.read_csv("reprohum_reg_data.csv")

trial_orders = {}

for i in range(num_lists):

    trial_ids = trial_df.loc[trial_df["list_id"] == i+1]["trial_id"]
    trial_ids = list(trial_ids)
    print(i+1, "before: ", trial_ids)


    this_list = [start_trials[i+1]]

    shuffle(trial_ids)

    for x in trial_ids:
        if x == start_trials[i+1]:
            continue
        else:
            this_list.append(x)
    print(i+1, "shuffled: ", this_list, len(this_list), len(list(set(this_list))))
    trial_orders[i+1] = this_list

columns = [f"trial_{x}" for x in range(1, 25)]

result_df = pd.DataFrame.from_dict(trial_orders, orient='index', columns=columns)
result_df = result_df.rename_axis('list_id')
result_df.to_csv("trial_orders.csv")