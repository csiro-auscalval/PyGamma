import io
import copy

from insar.logs import STATUS_LOGGER as LOG

class GammaParFile:
    par_dict = {}  # dict of parameter key and value
    par_keys = []  # ordered list of keys (dict is not keeping sequence)

    def __init__(self, *args):
        par_dict = {}
        par_keys = []

        if len(args) > 0:
            input_file = args[0]
            if isinstance(input_file, str):
                pf = io.open(input_file, "r", encoding="utf8", errors="ignore")
                file_name = True
            else:
                try:
                    if isinstance(input_file, io.TextIOWrapper):
                        pf = input_file
                        file_name = False
                    else:
                        LOG.error("Invalid input_file")
                        return -1
                except:
                    try:
                        if sys.version_info[0] < 3:
                            if isinstance(input_file, file):
                                pf = input_file
                                file_name = False
                            else:
                                LOG.error("Invalid input_file")
                                return -1
                        else:
                            if isinstance(input_file, io.IOBase):
                                pf = input_file
                                file_name = False
                            else:
                                LOG.error("Invalid input_file")
                                return -1
                    except:
                        LOG.error("Invalid input_file")
                        return -1
            kv = []
            pv = []
            line = pf.readline()  # read line

            while line:
                if (
                    line[0] == "#" or len(line.strip()) == 0
                ):  # ignore blank lines and lines starting with #
                    line = pf.readline()  # read next line
                    continue

                kv = line.partition(
                    ":"
                )  # use partition builtin function split line into a tuple of 3 strings (keyword, sep, value)
                if kv is None or len(kv) < 3 or kv[1] == "":
                    line = pf.readline()  # read next line
                    continue

                key = kv[0].strip()
                par_keys.append(key)  # save keys
                p2 = (
                    kv[2].split("#")[0].strip()
                )  # parse only everything in front of a comment and remove leading and trailing whitespace
                if p2 == "":
                    par_dict[key] = [""]
                    line = pf.readline()  # read next line
                    continue

                if p2[0] == "[":  # test if data are in list notation
                    try:
                        pv = ast.literal_eval(p2)  # interpret string as a list and convert to a list
                    except:
                        LOG.error(f"String value cannot be interpreted as a Python list: {p2} {type(p2)}")
                        return -1
                elif p2[0] == "{":  # test if data are in dictionary notation
                    try:
                        pv = ast.literal_eval(p2)
                    except:
                        LOG.error(f"String value cannot be interpreted as a Python list: {p2} {type(p2)}")
                        return -1
                elif (
                    len(p2.split('"')) == 3
                ):  # test if value is in quotes, create a list and add the value
                    pv = []
                    pv.append(p2)
                else:
                    params = p2.replace(
                        ",", " "
                    )  # replace commas with whitespace for compatibility
                    pv = (
                        params.split()
                    )  # split remaining parameters using whitespace as delimiter
                    for i in range(len(pv)):
                        pv[i] = pv[i].strip()  # remove any whitespace from each parameter

                par_dict[key] = pv  # store in dictionary
                line = pf.readline()  # read next line

            self.par_dict = par_dict  # store dict
            self.par_keys = par_keys  # store keyword list

            if file_name:
                pf.close()

    def dump(self):
        for key in self.par_keys:
            LOG.info("%s:\t\t %s" % (key, self.par_dict[key]))
        return

    def get_dict(self, **kwargs):
        key_in = ""
        if "key" in kwargs:
            key_in = kwargs["key"]

        index_in = ""
        index_num = True
        if "index" in kwargs:
            if kwargs["index"] != 0 and kwargs["index"] != "0":
                if isinstance(kwargs["index"], str):
                    index_in = "_" + kwargs["index"]
                else:
                    index_in = "_" + str(kwargs["index"])
            else:
                index_num = False

        if is_ordered:
            d_out = OrderedDict()
        else:
            d_out = {}

        for key in self.par_keys:
            if key_in in key:
                if index_in in key[-len(index_in) :]:
                    d_out[key] = self.par_dict[key]
                    if not index_num:
                        for num in range(len(self.par_keys)):
                            txt = "_" + str(num)
                            if txt in key[-len(txt) :]:
                                d_out.pop(key, None)

        return d_out

    def get_value(self, key, **kwargs):
        # get value for key
        if key in self.par_dict:
            value_list = copy.copy(self.par_dict[key])

            if "dtype" in kwargs:
                for i in range(len(value_list)):
                    try:
                        value_list[i] = kwargs["dtype"](value_list[i])
                    except:
                        try:
                            value_list[i] = kwargs["dtype"](float(value_list[i]))
                        except:
                            continue

            if "index" in kwargs:
                output = value_list[kwargs["index"]]
                return output

            if len(value_list) == 1:
                output = value_list[0]
                return output
            else:
                return value_list
        else:
            return None  # if key does not exist

    def remove_key(self, key):
        self.par_dict.pop(key, None)

        try:
            item = self.par_keys.index(key)
            del self.par_keys[item]
        except:
            pass
        return

    def set_value(self, key, value, **kwargs):
        if not key in self.par_keys:
            self.par_keys.append(key)  # append new key to list

        if "index" in kwargs:
            if key in self.par_dict:
                self.par_dict[key][kwargs["index"]] = str(value)
            else:
                self.par_dict[key] = [str(value)]
        else:
            if isinstance(value, list):
                self.par_dict[key] = list(map(str, value))
            else:
                self.par_dict[key] = [str(value)]
        return

    def update_from_dict(self, d_in):
        key_not_found = []

        for key_in in d_in.keys():
            key_found = False
            for key_pf in self.par_dict.keys():
                if key_in == key_pf:
                    self.par_dict[key_pf] = d_in[key_in]
                    key_found = True
                    break
            if not key_found:
                key_not_found.append(key_in)

        if key_not_found:
            LOG.info(
                "WARNING: One or several keywords in the input dictionary were not found in the ParFile object and were ignored:"
            )
            LOG.info(key_not_found)
        return

    def write_par(self, output_file):
        # write key/value pairs separated by :
        if isinstance(output_file, str):
            pf = io.open(output_file, "w+", encoding="utf8", errors="ignore")
            file_name = True
        else:
            try:
                if isinstance(output_file, io.TextIOWrapper):
                    pf = output_file
                    file_name = False
                else:
                    LOG.error("Invalid output_file")
                    return
            except:
                try:
                    if sys.version_info[0] < 3:
                        if isinstance(output_file, file):
                            pf = output_file
                            file_name = False
                        else:
                            LOG.error("Invalid output_file")
                            return
                    else:
                        if isinstance(output_file, io.IOBase):
                            pf = output_file
                            file_name = False
                        else:
                            LOG.error("Invalid output_file")
                            return
                except:
                    LOG.error("Invalid output_file")
                    return
        tstr = ""
        for key in self.par_keys:
            if (type(self.par_dict[key])) == list:
                for i in range(len(self.par_dict[key])):
                    if i == 0:
                        tstr = self.par_dict[key][i]
                    else:
                        tstr = "%s %s" % (tstr, self.par_dict[key][i])
                line = "%s: %s\n" % (key, tstr)
            else:
                line = "%s: %s\n" % (key, self.par_dict[key])

            if sys.version_info[0] == 2:
                pf.write(line.decode("utf-8"))
            else:
                pf.write(line)

        if file_name:
            pf.close()
        return
