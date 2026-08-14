def db_to_dict(obj):
    if not obj:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
