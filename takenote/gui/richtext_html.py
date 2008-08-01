"""
  HTML reader/writer for RichText
"""


import re

from HTMLParser import HTMLParser


from takenote.gui.textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags

from takenote.gui.richtextbuffer import \
     IGNORE_TAGS, \
     add_child_to_buffer, \
     RichTextBuffer, \
     RichTextImage, \
     RichTextHorizontalRule, \
     RichTextError




class HtmlError (StandardError):
    """Error for HTML parsing"""
    pass


class HtmlBuffer (HTMLParser):
    """Read and write HTML for a RichTextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self._out = out
        self._mod_tags = "biu"
        self._mod_tag2buffer_tag = {
            "b": "Bold",
            "i": "Italic",
            "u": "Underline"}
        self._buffer_tag2mod_tag = {
            "Bold": "b",
            "Italic": "i",
            "Underline": "u"
            }
        self._newline = False
        
        self._tag_stack = []
        self._buffer = None
        self._text_queue = []
        self._within_body = False
        
        self._entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt"),
                                (" ", "nbsp")]
        self._entity2char = {}
        for ch, name in self._entity_char_map:
            self._entity2char[name] = ch
        
        self._charref2char = {"09": "\t"}
        
        
        
    
    def set_output(self, out):
        """Set the output stream for HTML"""
        self._out = out
    
    
    def read(self, infile):
        """Read from stream infile to populate textbuffer"""
        self._text_queue = []
        self._within_body = False
        self._buffer_contents = []
        
        for line in infile:
            self.feed(line)

            # yeild items read so far
            for item in self._buffer_contents:
                yield item
            self._buffer_contents[:] = []
        
        self.close()
        self.flush_text()

        # yeild remaining items so far
        for item in self._buffer_contents:
            yield item
        self._buffer_contents[:] = []
        


    def flush_text(self):
        if len(self._text_queue) > 0:
            self._buffer_contents.append(("text", None,
                                          "".join(self._text_queue)))
            self._text_queue[:] = []

    def queue_text(self, text):
        self._text_queue.append(text)

    def append_buffer_item(self, kind, htmltag, tagstr, param):
        self.flush_text()
        self._tag_stack.append((htmltag, tagstr))
        self._buffer_contents.append((kind, None, param))

    
    def handle_starttag(self, htmltag, attrs):
        """Callback for parsing a starting HTML tag"""

        # NOTE: right now I have a 1:1 correspondence b/w html tags and
        # richtext tags.  I should remove this.
        
        self._newline = False

        if htmltag == "html":
            # ignore html tag
            pass
        
        elif htmltag == "body":
            # note that we are no within the body tag
            self._within_body = True
        
        elif htmltag in self._mod_tag2buffer_tag:
            # simple font modifications (b/i/u)
            
            tagstr = self._mod_tag2buffer_tag[htmltag]
            self.append_buffer_item("beginstr", htmltag, tagstr, tagstr)

        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("font-size"):
                        size = int(value.split(":")[1].replace("pt", ""))
                        tagstr = "size " + str(size)
                        
                    elif value.startswith("font-family"):
                        tagstr = value.split(":")[1].strip()
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.append_buffer_item("beginstr", htmltag, tagstr, tagstr)

        
        elif htmltag == "div":
            # text justification
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("text-align"):
                        align = value.split(":")[1].strip()

                        # TODO: simplify
                        if align == "left":
                            tagstr = "Left"
                        elif align == "center":
                            tagstr = "Center"
                        elif align == "right":
                            tagstr = "Right"
                        elif align == "justify":
                            tagstr = "Justify"
                        else:
                            raise HtmlError("unknown justification '%s'"
                                            % align)
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.append_buffer_item("beginstr", htmltag, tagstr, tagstr)

            
        elif htmltag == "br":
            # insert newline
            self.queue_text("\n")
            self._newline = True
            self._tag_stack.append((htmltag, None))

        elif htmltag == "hr":
            # horizontal break
            hr = RichTextHorizontalRule()
            self.append_buffer_item("anchor", htmltag, None, (hr, None))

        
        elif htmltag == "img":
            # insert image
            img = RichTextImage()
            width, height = None, None
            
            for key, value in attrs:
                if key == "src":
                    img.set_filename(value)
                elif key == "width":
                    try:
                        width = int(value)
                    except ValueError, e:
                        raise HtmlError("expected integer for image width '%s'" % value)
                elif key == "height":
                    try:
                        height = int(value)
                    except ValueError, e:
                        raise HtmlError("expected integer for image height '%s'" % value)
                else:
                    HtmlError("unknown attr key '%s'" % key)

            img.set_size(width, height)
            self.append_buffer_item("anchor", htmltag, None, (img, None))

            
        else:
            self._tag_stack.append((htmltag, None))
            raise HtmlError("WARNING: unhandled tag '%s'" % htmltag)
        
        


    def handle_endtag(self, htmltag):
        """Callback for parsing a ending HTML tag"""
        
        self._newline = False
        if htmltag in ("html", "body") or not self._within_body:
            return

        htmltag2, tagstr = self._tag_stack.pop()
        
        # ensure closing tags match opened tags
        if htmltag2 != htmltag:
            raise HtmlError("closing tag does not match opening tag")        
        
        if tagstr is not None:
            self.flush_text()
            self._buffer_contents.append(("endstr", None, tagstr))
        
    
    
    def handle_data(self, data):
        """Callback for character data"""

        if not self._within_body:
            return
        
        if self._newline:
            data = re.sub("\n[\n ]*", "", data)
            self._newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        self.queue_text(data)

    
    def handle_entityref(self, name):
        if not self._within_body:
            return
        self.queue_text(self._entity2char.get(name, ""))
    
    
    def handle_charref(self, name):
        if not self._within_body:
            return
        self.queue_text(self._charref2char.get(name, ""))
        
    
    def write(self, textbuffer):
        self._buffer = textbuffer
        
        self._out.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>""")
        
        for kind, it, param in normalize_tags(iter_buffer_contents(self._buffer,
                                                                   None,
                                                                   None,
                                                                   IGNORE_TAGS)):
            if kind == "text":
                text = param
                
                # TODO: could try to speed this up
                text = text.replace("&", "&amp;")
                text = text.replace(">", "&gt;")
                text = text.replace("<", "&lt;")
                text = text.replace("\n", "<br/>\n")
                text = text.replace("\t", "&#09;")
                text = text.replace("  ", " &nbsp;")
                self._out.write(text)
            
            elif kind == "begin":
                tag = param
                self.write_tag_begin(tag)
                
            elif kind == "end":
                tag = param
                self.write_tag_end(tag)
            
            elif kind == "anchor":
                child = param[0]

                if isinstance(child, RichTextImage):
                    # write image
                    size_str = ""
                    size = child.get_size()
                        
                    if size[0] is not None:
                        size_str += " width=\"%d\"" % size[0]
                    if size[1] is not None:
                        size_str += " height=\"%d\"" % size[1]
                        
                    self._out.write("<img src=\"%s\" %s />" % 
                                   (child.get_filename(), size_str))

                elif isinstance(child, RichTextHorizontalRule):
                    self._out.write("<hr/>")
                    
                else:
                    # warning
                    #TODO:
                    print "unknown child element", child
            
            elif kind == "pixbuf":
                pass
            else:
                raise Exception("unknown kind '%s'" % str(kind))
        
        self._out.write("</body></html>")
        
    
    def write_tag_begin(self, tag):
        if tag in self._buffer.mod_tags:
            self._out.write("<%s>" % self._buffer_tag2mod_tag[tag.get_property("name")])
        else:
            if tag in self._buffer.size_tags:
                self._out.write("<span style='font-size: %dpt'>" % 
                          tag.get_property("size-points"))
            elif tag in self._buffer.family_tags:
                self._out.write("<span style='font-family: %s'>" % 
                          tag.get_property("family"))
            elif tag in self._buffer.justify_tags:
                if tag == self._buffer.left_tag:
                    text = "left"
                elif tag == self._buffer.center_tag:
                    text = "center"
                elif tag == self._buffer.right_tag:
                    text = "right"
                else:
                    text = "justify"
                self._out.write("<div style='text-align: %s'>" % text)
            elif tag.get_property("name") in IGNORE_TAGS:
                pass
            else:
                raise HtmlError("unknown tag '%s'" % tag.get_property("name"))
                
        
    def write_tag_end(self, tag):
        if tag in self._buffer.mod_tags:
            self._out.write("</%s>" % self._buffer_tag2mod_tag[tag.get_property("name")])
        elif tag in self._buffer.justify_tags:
            self._out.write("</div>")
        else:
            self._out.write("</span>")


