from collections import OrderedDict


def make_metadata_ordered_dict(keys, metadata, get_from=None):
    """Create an OrderedDict with given keys, and values

    extracted from metadata list (or being None if not present
    in metadata list. If there is a need to choose values among
    subfields (delimited by ',') then get_from tells from which
    subfield the data should be used. This function will demand
    all keys existing in dictionary to be updated - if you want
    to loosen this requirement you can specify which fields are
    not compulsory, and should be assigned with None value (as to
    import flags from VCF file).
    """
    dict_to_fill = OrderedDict(
        (
            (key, None)
            for key in keys
        )
    )

    for entry in metadata:
        try:
            # given entry is an assignment
            key, value = entry.split('=')
            if get_from is not None and ',' in value:
                value = float(value.split(',')[get_from])
        except ValueError:
            # given entry is a flag
            key = entry
            value = True

        if key in keys:
            dict_to_fill[key] = value

    return dict_to_fill
