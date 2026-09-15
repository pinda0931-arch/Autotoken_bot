from config import ADMIN_ID, AUTHORIZED_USERS, STEALER_ACCESS_USERS
import config

def is_authorized(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    if config.GLOBAL_FREE:
        return True
    return user_id in AUTHORIZED_USERS

def grant_access(user_id: int):
    AUTHORIZED_USERS.add(user_id)

def revoke_access(user_id: int):
    AUTHORIZED_USERS.discard(user_id)

def grant_stealer_access(user_id: int):
    config.STEALER_ACCESS_USERS.add(user_id)

def revoke_stealer_access(user_id: int):
    config.STEALER_ACCESS_USERS.discard(user_id)

def set_global_free(val: bool):
    config.GLOBAL_FREE = val
