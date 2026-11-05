try:
    from app.games.fields_of_fire.validator import FieldsOfireValidator
    print("FieldsOfireValidator imported OK")
except ImportError as e:
    print(f"FieldsOfireValidator failed: {e}")
    try:
        from app.games.fields_of_fire.validator import FieldsOfFireValidator
        print("FieldsOfFireValidator imported OK")
    except ImportError as e2:
        print(f"FieldsOfFireValidator also failed: {e2}")