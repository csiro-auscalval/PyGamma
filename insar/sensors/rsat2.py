

# Example: RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC
# Parts: RS2_OK{order key}_PK{product key}_DK{delivery key}_{beam mode}_{acquisition date}_{start time}_{polarisation}_{product type}
ANY_DATA_PATTERN = (
    r"^RS2_"
    r"OK(?P<order_key>[0-9]+)_"
    r"PK(?P<product_key>[0-9]+)_"
    r"DK(?P<delivery_key>[0-9]+)_"
    r"(?P<beam_mode>[^_]+)_"
    r"(?P<start_date>[0-9]{8})_"
    r"(?P<start_time>[0-9]{6})_"
    r"(?P<polarisation>VV|HH|HV|VH)_"
    r"(?P<product>SLC)$"
)

