"""INIT."""

def is_topic_allowed(topic_requested: str, topic_allowed: str) -> bool:
    req_split = topic_requested.split("/")
    allowed_split = topic_allowed.split("/")
    ret = True
    for i in range(max(len(req_split), len(allowed_split))):
        try:
            a_aux = req_split[i]
            b_aux = allowed_split[i]
        except IndexError:
            ret = False
            break
        if b_aux == "#":
            break
        if b_aux in ("+", a_aux):
            continue
        ret = False
        break
    return ret