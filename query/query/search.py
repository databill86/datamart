import hashlib
import logging
import os
import pickle
import tempfile
from datamart_profiler import process_dataset


logger = logging.getLogger(__name__)


BUF_SIZE = 128000


class ClientError(ValueError):
    """Error in query sent by client.
    """


def get_profile_data(filepath, metadata=None):
    # hashing data
    sha1 = hashlib.sha1()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    hash_ = sha1.hexdigest()

    # checking for cached data
    cached_data = os.path.join('/cache', hash_)
    if os.path.exists(cached_data):
        return pickle.load(open(cached_data, 'rb'))

    # profile data and save
    data_profile = process_dataset(filepath, metadata)
    pickle.dump(data_profile, open(cached_data, 'wb'))
    return data_profile


def handle_data_parameter(data):
    """
    Handles the 'data' parameter.

    :param data: the input parameter
    :return: (data_path, data_profile, tmp)
      data_path: path to the input data
      data_profile: the profiling (metadata) of the data
      tmp: True if data_path points to a temporary file
    """

    if not isinstance(data, (str, bytes)):
        raise ClientError("The parameter 'data' is in the wrong format")

    tmp = False
    if not os.path.exists(data):
        # data represents the entire file
        logger.warning("Data is not a path!")

        tmp = True
        temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        temp_file.write(data)
        temp_file.close()

        data_path = temp_file.name
        data_profile = get_profile_data(data_path)

    else:
        # data represents a file path
        logger.warning("Data is a path!")
        if os.path.isdir(data):
            # path to a D3M dataset
            data_file = os.path.join(data, 'tables', 'learningData.csv')
            if not os.path.exists(data_file):
                raise ClientError("%s does not exist" % data_file)
            else:
                data_path = data_file
                data_profile = get_profile_data(data_file)
        else:
            # path to a CSV file
            data_path = data
            data_profile = get_profile_data(data)

    return data_path, data_profile, tmp