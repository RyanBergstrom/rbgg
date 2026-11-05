#!/usr/bin/env python
import sys
try:
    from app.games.fields_of_fire.validator import FieldsOfireValidator
    print("Using FieldsOfireValidator")
except ImportError:
    from app.games.fields_of_fire.validator import FieldsOfFireValidator
    print("Using FieldsOfFireValidator")

from app.games.fields_of_fire.validator import FieldsOfireValidator as V2
print("V2 type:", type(V2))