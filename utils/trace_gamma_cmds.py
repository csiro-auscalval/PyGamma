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

args = parser.parse_args()
jsonl_path = Path(args.path)
json_log = [json.loads(line) for line in jsonl_path.open("r").read().splitlines()]

for i in json_log:
    if "command" in i:
        cmd_params = eval(i["command"])  # Convert str to the actual list
        cmd = Path(cmd_params[0]).name
        cmd_params = cmd_params[1:]

    elif "cmd" in i:
        cmd = Path(i["cmd"]).name
        cmd_params = i["cmd_list"][1:] if "cmd_list" in i else []

    else:
        continue

    print(cmd, *cmd_params)
