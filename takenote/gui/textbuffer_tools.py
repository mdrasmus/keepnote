





#=============================================================================
# functions for iterating and inserting into textbuffers

def iter_buffer_contents(textbuffer, start=None, end=None,
                         ignore_tags={}):
    """Iterate over the items of a textbuffer

    textbuffer -- buffer to iterate over
    start      -- starting position (TextIter)
    end        -- ending position (TextIter)
    """

    # initialize iterators
    if start is None:
        it = textbuffer.get_start_iter()
    else:
        it = start.copy()
    last = it.copy()

    if end is None:
        end = textbuffer.get_end_iter()


    # yield opening tags at begining of region
    for tag in it.get_tags():
        if tag.get_property("name") in ignore_tags:
            continue
        yield ("begin", it, tag)
    
    while True:
        it2 = it.copy()    
        it.forward_to_tag_toggle(None)

        # yield child anchors between tags        
        while True:
            if it.get_offset() < end.get_offset():
                stop = it
            else:
                stop = end
            ret = it2.forward_search(ANCHOR_CHAR, (), stop)
            
            if ret is None:
                yield ("text", it2, it2.get_text(stop))
                break
            
            a, b = ret
            anchor = a.get_child_anchor()
            
            # yield text in between tags
            yield ("text", it2, it2.get_text(a))
            if anchor is not None:
                yield ("anchor", a, (anchor, anchor.get_widgets()))
            else:
                yield ("pixbuf", a, a.get_pixbuf())
            it2 = b
        
        # stop iterating if we have pasted end of region
        if it.get_offset() > end.get_offset():
            break
        
        # yield closing tags
        for tag in it.get_toggled_tags(False):
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("end", it, tag)

        # yield opening tags
        for tag in it.get_toggled_tags(True):
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("begin", it, tag)
        
        last = it.copy()
        
        if it.equal(end):
            break
    
    # yield tags that have not been closed yet
    toggled = set(end.get_toggled_tags(False))
    for tag in end.get_tags():
        if tag not in toggled:
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("end", end, tag)


def buffer_contents_iter_to_offset(contents):
    """Converts to iters of a content list to offsets"""
    
    for kind, it, param in contents:
        yield (kind, it.get_offset(), param)
    

def normalize_tags(items):
    """Normalize open and close tags to ensure proper nesting
       This is especially useful for saving to HTML
    """

    open_stack = []

    for item in items:
        kind, it, param = item
        if kind == "begin":
            open_stack.append(param)
            yield item

        elif kind == "end":

            # close any open out of order tags
            reopen_stack = []
            while param != open_stack[-1]:
                reopen_stack.append(open_stack.pop())
                tag2 = reopen_stack[-1]
                yield ("end", it, tag2)

            # close current tag
            open_stack.pop()
            yield item

            # reopen tags
            for tag2 in reversed(reopen_stack):
                open_stack.append(tag2)
                yield ("begin", it, tag2)

        else:
            yield item


 

def insert_buffer_contents(textbuffer, pos, contents, add_child):
    """Insert a content list into a RichTextBuffer"""
    
    textbuffer.place_cursor(pos)
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "text":
            # insert text
            textbuffer.insert_at_cursor(param)
            
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "anchor":
            # insert widget            
            it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            anchor = param[0].copy()
            add_child(textbuffer, it, anchor)
            
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "begin":
            tags[param] = textbuffer.get_iter_at_mark(textbuffer.get_insert()).get_offset()
            
        elif kind == "end":
            start = textbuffer.get_iter_at_offset(tags[param])
            end = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            textbuffer.apply_tag(param, start, end)


def buffer_contents_apply_tags(textbuffer, contents):
    """Apply tags to a textbuffer"""
    
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "begin":
            tags[param] = textbuffer.get_iter_at_offset(offset)
            
        elif kind == "end":
            start = tags[param]
            end = textbuffer.get_iter_at_offset(offset)
            textbuffer.apply_tag(param, start, end)

