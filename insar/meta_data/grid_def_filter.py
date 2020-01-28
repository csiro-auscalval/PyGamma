#!/usr/bin/env python

from pathlib import Path


def grid_processing_list():
    return {
        'T002D': [f"F{frame:02}S" for frame in range(9, 27)],
        'T016D': [f"F{frame:02}S" for frame in range(16, 32)],
        'T017D': [f"F{frame:02}S" for frame in range(12, 29)],
        'T031D': [f"F{frame:02}S" for frame in range(14, 28)],
        'T045D': [f"F{frame:02}S" for frame in range(19, 36)],
        'T046D': [f"F{frame:02}S" for frame in range(10, 29)],
        'T060D': [f"F{frame:02}S" for frame in range(10, 30)],
        'T061D': [f"F{frame:02}S" for frame in range(17, 26)],
        'T074D': [f"F{frame:02}S" for frame in range(23, 32)],
        'T075D': [f"F{frame:02}S" for frame in range(10, 27)],
        'T089D': [f"F{frame:02}S" for frame in range(15, 31)],
        'T090D': [f"F{frame:02}S" for frame in range(14, 29)],
        'T104D': [f"F{frame:02}S" for frame in range(9, 27)],
        'T118D': [f"F{frame:02}S" for frame in range(17, 34)],
        'T119D': [f"F{frame:02}S" for frame in range(12, 29)],
        'T133D': [f"F{frame:02}S" for frame in range(9, 29)],
        'T134D': [f"F{frame:02}S" for frame in range(16, 24)],
        'T147D': [f"F{frame:02}S" for frame in range(21, 36)],
        'T148D': [f"F{frame:02}S" for frame in range(9, 28)],
        'T162D': [f"F{frame:02}S" for frame in range(12, 31)],
        'T163D': [f"F{frame:02}S" for frame in range(15, 29)],
    }


def main(grid_data_dir: Path, out_dir: Path):

    for track, frame_list in grid_processing_list().items():
        with open(out_dir.joinpath(f"input_list_{track}.txt").as_posix(), "w") as fid:
            for frame in frame_list:
                grid_name = grid_data_dir.joinpath(f"{track}_{frame}.shp")
                if grid_name.exists():
                    fid.write(grid_name.as_posix())
                    fid.write("\n")


if __name__ == '__main__':

    _dir = Path('/g/data/u46/users/pd1813/INSAR/shape_files/final_grid_def_with_bursts')
    out_dir = Path('/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/input_files')
    main(_dir, out_dir)
