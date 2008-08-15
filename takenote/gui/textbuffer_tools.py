"""

 Functions for iterating and inserting into textbuffers

"""
import sys
sys.path.append("../..")

from takenote.linked_list import LinkedList

# TextBuffer uses this char for anchors and pixbufs
ANCHOR_CHAR = u'\ufffc'



class PushIter (object):
    """Wrap an iterator in another iterator that allows one to push new
       items onto the front of the iteration stream"""
    
    def __init__(self, it):
        self._it = iter(it)
        self._queue = LinkedList()

    def __iter__(self):
        return self
        
    def next(self):
        if len(self._queue) > 0:
            return self._queue.pop_front()
        else:
            return self._it.next()

    def push(self, item):
        """Push a new item onto the front of the iteration stream"""
        self._queue.append(item)


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
                text = it2.get_text(stop)
                if len(text) > 0:
                    yield ("text", it2, text)
                break
            
            a, b = ret
            anchor = a.get_child_anchor()
            
            # yield text in between tags
            text = it2.get_text(a)
            if len(text) > 0:
                yield ("text", it2, text)
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


def _normalize_close(open_stack, closing_tags):
    """Close the tags in closing_tags and reopen any tags that did not need
       to be closed

       <z><b><x><c><y><d> </d></c></b> ...
       open               closing tags
       stack

       <z><b><x><c><y><d> </d></y></c></x></b> <x><y>
                          closing              reopen

    """

    closing_tags = set(closing_tags)

    # close tags until all closing_tags are closed
    reopen_stack = []
    while len(closing_tags) > 0:
        tag = open_stack.pop()
        if tag in closing_tags:
            # mark as closed
            closing_tags.remove(tag)
        else:
            # remember to reopen
            reopen_stack.append(tag)
        yield ("end", None, tag)

    # reopen tags
    for tag in reversed(reopen_stack):
        open_stack.append(tag)
        yield ("begin", None, tag)

    

def normalize_tags(contents, is_stable_tag=lambda tag: False):
    """Normalize open and close tags to ensure proper nesting
       This is especially useful for saving to HTML

       is_stable_tag -- a function that returns True iff a tag should not
       be touched (``stable'').

       NOTE: All iterators will be turned to None's.  Since were are changing
       tag order, iterators no longer make sense

       NOTE: assumes we do not have any 'beginstr' and 'endstr' items
    """

    open_stack = []
    contents = PushIter(contents)

    for item in contents:
        kind, it, param = item
        
        if kind == "begin":
            
            if is_stable_tag(param):
                # if stable tag, skim ahead to see its closing tag
                stable_span = LinkedList()
                within_closes = set()
                for item2 in contents:
                    stable_span.append(item2)
                    if item2[0] == "end":
                        # look at closing tags
                        if item2[2] == param:
                            # found matching stable close
                            break

                        else:
                            # record tags that close within the stable_span
                            within_closes.add(item2[2])
                
                # push items back on contents stream
                for item2 in reversed(stable_span):
                    contents.push(item2)

                # define tag classes
                # preopen = open_stack

                # preopen_inside = preopen's with a close in stable_span
                preopen_inside = []
                for tag in open_stack:
                    if tag in within_closes:
                        preopen_inside.append(tag)

                print preopen_inside
                
                # preopen_outside = set(preopen) - (preopen_inside)

                # close preopen_inside
                for item2 in _normalize_close(open_stack, preopen_inside):
                    yield item2

                # yield stable open
                open_stack.append(param)
                yield ("begin", None, param)
                
                # reopen preopen_inside
                for tag in preopen_inside:
                    open_stack.append(tag)
                    yield ("begin", None, tag)
                
            else:                
                # yield item unchanged
                open_stack.append(param)
                yield ("begin", None, param)

        elif kind == "end":
            
            for item2 in _normalize_close(open_stack, [param]):
                yield item2

        else:
            yield (kind, None, param)




#def remove_empty_text(contents):
#    """Remove spurious text items that are empty"""



# NOTE: I have a add_child() function to abstract the insertion of child
# objects.  I will also need a lookup_tag() function for the case where I am
# adding a tag that is currently not registered.  This will happen when I add
# a new kind "tagstr", which will be interpreted by tag_lookup
# This is needed because my textbuffer has special code for creating certain
# new tags and I don't want to make that assumption with this function.
# 'textbuffer' should have a class of simply TextBuffer (not RichTextBuffer)

def insert_buffer_contents(textbuffer, pos, contents, add_child,
                           lookup_tag=lambda tagstr: None):
    """Insert a content list into a RichTextBuffer"""
    
    textbuffer.place_cursor(pos)
    tags = {}
    tagstrs = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for kind, offset, param in contents:
        # NOTE: offset is ignored
        
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
                it2.backward_chars(1) #len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "begin":
            # remember the starting position of a tag
            tags[param] = textbuffer.get_iter_at_mark(
                textbuffer.get_insert()).get_offset()
            
        elif kind == "end":
            # apply tag
            start = textbuffer.get_iter_at_offset(tags[param])
            end = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            textbuffer.apply_tag(param, start, end)
            
        elif kind == "beginstr":
            # remember the starting position of a tag referred to by a string

            lst = tagstrs.get(param, None)
            if lst is None:
                lst = []
                tagstrs[param] = lst
            lst.append(textbuffer.get_iter_at_mark(
                textbuffer.get_insert()).get_offset())

        elif kind == "endstr":
            # apply tag referred to by a string
            tag = lookup_tag(param)

            if tag:
                offset = tagstrs[param].pop()
                start = textbuffer.get_iter_at_offset(offset)
                end = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                textbuffer.apply_tag(tag, start, end)


def buffer_contents_apply_tags(textbuffer, contents):
    """Apply tags to a textbuffer"""
    
    tags = {}
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "begin":
            tags[param] = textbuffer.get_iter_at_offset(offset)
            
        elif kind == "end":
            start = tags[param]
            end = textbuffer.get_iter_at_offset(offset)
            textbuffer.apply_tag(param, start, end)



#=============================================================================
# testing

if __name__ == "__main__":

    it = PushIter(xrange(10))

    for i in it:

        if i == 3:
            it.push("a")
            it.push("b")
            it.push("c")
        print i


#=============================================================================
# EXTRA CODE TO DELETE WHEN NO LONGER NEEDED

'''
            # close any open out of order tags
            reopen_stack = []
            while param != open_stack[-1]:
                reopen_stack.append(open_stack.pop())
                tag = reopen_stack[-1]
                yield ("end", it, tag)

            # close current tag
            open_stack.pop()
            yield item

            # reopen tags
            for tag in reversed(reopen_stack):
                open_stack.append(tag)
                yield ("begin", it, tag)
            '''


