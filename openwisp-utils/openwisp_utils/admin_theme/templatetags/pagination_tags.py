from django import template

register = template.Library()

@register.simple_tag
def get_page_window(cl, window_size=3):
    """
    Returns a list of page numbers (0-based) around the current page,
    in blocks of `window_size`. Example:
    - Page 0 → [0,1,2]
    - Page 2 → [0,1,2]
    - Page 3 → [3,4,5]
    """
    current = cl.page_num-1
    total = cl.paginator.num_pages

    # Figure out which block we are in
    block_start = (current // window_size) * window_size
    block_end = min(block_start + window_size, total)
    return list(range(block_start, block_end))

