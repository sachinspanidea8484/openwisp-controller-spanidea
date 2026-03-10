from django import template

register = template.Library()

@register.simple_tag
def page_range_display(cl):
    start = (cl.page_num-1) * cl.list_per_page + 1
    end = start + len(cl.result_list) - 1
    return f"{start}-{end} of {cl.result_count}"
