import json
import argparse
from pathlib import Path

if __name__ != "__main__":
    raise Exception("This is a script and shouldn't be imported like a module")

parser = argparse.ArgumentParser(
    description="Extract the sequence of gamma commands from the insar JSON Lines log (insar-log.jsonl)"
)
parser.add_argument(
    "path",
    type=str,
    help="The path to the gamma log file",
)
parser.add_argument(
    "id",
    type=str,
    nargs="+",
    help="Specifies a property name which uniquely identifies tasks, which is used to filter commands by task",
)

args = parser.parse_args()
ids = args.id
jsonl_path = Path(args.path)
json_log = [json.loads(line) for line in jsonl_path.open("r").read().splitlines()]

task_entries = {}

for i in json_log:
    key = [None] * len(ids)
    for id_idx, id in enumerate(ids):
        pval = i[id] if id in i else None
        key[id_idx] = pval

    key = tuple(key)

    if key in task_entries:
        task_entries[key].append(i)
    else:
        task_entries[key] = [i]

for task_key, entries in task_entries.items():
    commands = []

    for i in entries:
        if "command" in i:
            cmd_params = eval(i["command"])  # Convert str to the actual list
            cmd = Path(cmd_params[0]).name
            cmd_params = cmd_params[1:]

        elif "cmd" in i:
            cmd = Path(i["cmd"]).name
            cmd_params = i["cmd_list"][1:] if "cmd_list" in i else []

        else:
            continue

        commands.append((cmd, cmd_params))

    if not commands:
        continue

    print("=" * 24)
    print("Taks ids:", *task_key)
    for (cmd, cmd_params) in commands:
        print("    ", cmd, *cmd_params)
