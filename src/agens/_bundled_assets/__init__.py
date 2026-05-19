# This package contains default assets (knowledge files, prompts, etc.)
# that are bundled with the agens distribution.
#
# At first launch, these files are copied into the user's runtime config
# directory (platformdirs.user_config_path) where they can be freely
# edited.  On subsequent upgrades, only *new* files are added — existing
# user files are never overwritten.
#
# Access these assets at runtime via importlib.resources:
#
#     from importlib.resources import files
#     root = files("agens._bundled_assets")
