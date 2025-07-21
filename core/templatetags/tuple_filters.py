from django import template

register = template.Library()

def dict_tuple_get(d, subj_id, class_id):
    if not isinstance(d, dict):
        return None
    return d.get((subj_id, class_id))

register.filter('dict_tuple_get', dict_tuple_get)
