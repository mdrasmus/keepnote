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
    
        self.out = out
        self.mod_tags = "biu"
        self.mod_tag2buffer_tag = {
            "b": "Bold",
            "i": "Italic",
            "u": "Underline"}
        self.buffer_tag2mod_tag = {
            "Bold": "b",
            "Italic": "i",
            "Underline": "u"
            }
        self.newline = False
        
        self.tag_stack = []
        self.buffer = None
        self.text_queue = []
        self.within_body = False
        
        self.entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt"),
                                (" ", "nbsp")]
        self.entity2char = {}
        for ch, name in self.entity_char_map:
            self.entity2char[name] = ch
        
        self.charref2char = {"09": "\t"}
        
        
        
    
    def set_output(self, out):
        """Set the output stream for HTML"""
        self.out = out
    
    
    def read(self, textbuffer, infile):
        """Read from stream infile to populate textbuffer"""
        self.buffer = textbuffer
        self.text_queue = []
        self.within_body = False
        
        for line in infile:
            self.feed(line)
        self.close()
        self.flush_text()
        
        self.buffer.place_cursor(self.buffer.get_start_iter())


    def flush_text(self):
        if len(self.text_queue) > 0:
            self.buffer.insert_at_cursor("".join(self.text_queue))
            self.text_queue[:] = []

    def queue_text(self, text):
        self.text_queue.append(text)
        
    
    def handle_starttag(self, tag, attrs):
        """Callback for parsing a starting HTML tag"""
        self.newline = False
        if tag == "html":
            return
        
        elif tag == "body":
            self.within_body = True
            return

        elif tag in ("hr", "br", "img"):
            mark = None
        else:
            self.flush_text()
            mark = self.buffer.create_mark(None, self.buffer.get_end_iter(),
                                           True)
        self.tag_stack.append((tag, attrs, mark))


    def handle_endtag(self, tag):
        """Callback for parsing a ending HTML tag"""
        
        self.newline = False
        if tag in ("html", "body") or not self.within_body:
            return

        
        # ensure closing tags match opened tags
        if self.tag_stack[-1][0] != tag:
            raise HtmlError("closing tag does not match opening tag")
        htmltag, attrs, mark = self.tag_stack.pop()
        
        
        
        if htmltag in self.mod_tag2buffer_tag:
            # get simple fonts b/i/u
            tag = self.buffer.lookup_mod_tag(self.mod_tag2buffer_tag[htmltag])
            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())

        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("font-size"):
                        size = int(value.split(":")[1].replace("pt", ""))
                        tag = self.buffer.lookup_size_tag(size)
                        
                    elif value.startswith("font-family"):
                        family = value.split(":")[1].strip()
                        tag = self.buffer.lookup_family_tag(family)
                    
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)            
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())
        
        elif htmltag == "div":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("text-align"):
                        align = value.split(":")[1].strip()
                        if align == "left":
                            tag = self.buffer.left_tag
                        elif align == "center":
                            tag = self.buffer.center_tag
                        elif align == "right":
                            tag = self.buffer.right_tag
                        elif align == "justify":
                            tag = self.buffer.fill_tag
                        else:
                            raise HtmlError("unknown justification '%s'" % align)
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())    
            
        elif htmltag == "br":
            # insert newline
            self.queue_text("\n")
            self.newline = True

        elif htmltag == "hr":
            # horizontal break
            self.flush_text()
            self.buffer.insert_hr()
        
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
            self.flush_text()
            self.buffer.insert_image(img)
            
        
        else:
            raise HtmlError("WARNING: unhandled tag '%s'" % htmltag)

        
        # delete mark created with start tag
        if mark is not None:
            self.buffer.delete_mark(mark)
        
    
    
    def handle_data(self, data):
        """Callback for character data"""

        if not self.within_body:
            return
        
        if self.newline:
            data = re.sub("\n[\n ]*", "", data)
            self.newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        self.queue_text(data)

    
    def handle_entityref(self, name):
        if not self.within_body:
            return
        self.queue_text(self.entity2char.get(name, ""))
    
    
    def handle_charref(self, name):
        if not self.within_body:
            return
        self.queue_text(self.charref2char.get(name, ""))
        
    
    def write(self, textbuffer):
        self.buffer = textbuffer
        
        self.out.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>""")
        
        for kind, it, param in normalize_tags(iter_buffer_contents(self.buffer,
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
                self.out.write(text)
            
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
                        
                    self.out.write("<img src=\"%s\" %s />" % 
                                   (child.get_filename(), size_str))

                elif isinstance(child, RichTextHorizontalRule):
                    self.out.write("<hr/>")
                    
                else:
                    # warning
                    #TODO:
                    print "unknown child element", child
            
            elif kind == "pixbuf":
                pass
            else:
                raise Exception("unknown kind '%s'" % str(kind))
        
        self.out.write("</body></html>")
        
    
    def write_tag_begin(self, tag):
        if tag in self.buffer.mod_tags:
            self.out.write("<%s>" % self.buffer_tag2mod_tag[tag.get_property("name")])
        else:
            if tag in self.buffer.size_tags:
                self.out.write("<span style='font-size: %dpt'>" % 
                          tag.get_property("size-points"))
            elif tag in self.buffer.family_tags:
                self.out.write("<span style='font-family: %s'>" % 
                          tag.get_property("family"))
            elif tag in self.buffer.justify_tags:
                if tag == self.buffer.left_tag:
                    text = "left"
                elif tag == self.buffer.center_tag:
                    text = "center"
                elif tag == self.buffer.right_tag:
                    text = "right"
                else:
                    text = "justify"
                self.out.write("<div style='text-align: %s'>" % text)
            elif tag.get_property("name") in IGNORE_TAGS:
                pass
            else:
                raise HtmlError("unknown tag '%s'" % tag.get_property("name"))
                
        
    def write_tag_end(self, tag):
        if tag in self.buffer.mod_tags:
            self.out.write("</%s>" % self.buffer_tag2mod_tag[tag.get_property("name")])
        elif tag in self.buffer.justify_tags:
            self.out.write("</div>")
        else:
            self.out.write("</span>")


