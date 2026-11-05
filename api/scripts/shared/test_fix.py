import sys
# Import the validator class - try both names
try:
    from app.games.fields_of_fire.validator import FieldsOfireValidator
    print("Using FieldsOfireValidator")
except ImportError:
    from app.games.fields_of_fire.validator import FieldsOfireValidator as FieldsOfireValidator2
    print("Using FieldsOfireValidator2")
    sys.exit(0)

# If we get here, FieldsOfireValidator imported OK
from app.games.fields_of_fire.validator import FieldsOfireValidator
print("FieldsOfireValidator imported successfully")