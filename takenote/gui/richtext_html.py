"""
  HTML reader/writer for RichText
"""


# python imports
import re
from HTMLParser import HTMLParser

# takenote imports
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
     RichTextError, \
     RichTextModTag, \
     RichTextFamilyTag, \
     RichTextSizeTag, \
     RichTextJustifyTag, \
     RichTextFGColorTag, \
     RichTextBGColorTag, \
     RichTextIndentTag



# constants
XHTML_HEADER = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>"""
XHTML_FOOTER = "</body></html>"


def convert_indent_tags(contents, tag_table):
    """Convert indent tags so that they nest like HTML tags"""

    indent = 0
    indent_closing = False

    # loop throught contents stream
    for item in contents:
        
        # if we are in the middle of a indent closing event, then the next
        # item determines what we should do
        if indent_closing:
            if item[0] == "anchor" or item[0] == "text":            
                # if we see "content" (anchors or text) (instead of
                # immediately opening a new indent) then we must close all
                # indents (i.e. indent=0)
                while indent > 0:
                    yield ("end", None, tag_table.lookup_indent(indent))
                    indent -= 1
                indent_closing = False

            elif item[0] == "begin":
                # if we see a begining tag then check to see if its an
                # indentation tag
                tag = item[2]
                
                if isinstance(tag, RichTextIndentTag):
                    # (A) if it is a new indentation  that is of lower indent
                    # close all indents until we match
                    next_indent = tag.get_indent()

                    while indent > next_indent:
                        yield ("end", None, tag_table.lookup_indent(indent))
                        indent -= 1
                
                    indent_closing = False
            else:
                # do nothing
                pass

        # yield items
        if item[0] == "begin" and \
           isinstance(item[2], RichTextIndentTag):
                # if item is a begining indent, open indents until we match
                tag = item[2]
                next_indent = tag.get_indent()

                # should be true since (A) should have executed
                assert next_indent >= indent
                
                while indent < next_indent:
                    # open new indents until we match level
                    indent += 1
                    assert indent > 0
                    yield ("begin", None, tag_table.lookup_indent(indent))

        elif item[0] == "end" and \
             isinstance(item[2], RichTextIndentTag):
                next_indent = item[2].get_indent()
                indent_closing = True
        else:
            yield item

    # close all remaining indents
    while indent > 0:
        yield ("end", None, tag_table.lookup_indent(indent))
        indent -= 1
    
        




class HtmlError (StandardError):
    """Error for HTML parsing"""
    pass


# TODO: may need to include support for ignoring information between
# <scirpt> and <style> tags

class HtmlBuffer (HTMLParser):
    """Read and write HTML for a RichTextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self._out = out
        self._mod_tags = "biu"
        self._html2buffer_tag = {
            "b": "bold",
            "i": "italic",
            "u": "underline",
            "nobr": "nowrap"}
        self._buffer_tag2html = {
            "bold": "b",
            "italic": "i",
            "underline": "u",
            "nowrap": "nobr"
            }
        self._justify = set([
            "left",
            "center",
            "right",
            "fill",
            "justify"])
        self._newline = False

        self._tag_stack = []
        self._butter_contents = []
        self._text_queue = []
        self._within_body = False
        self._partial = False
        self._indent = 0
        
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


    #===========================================
    # Reading HTML
    
    def read(self, infile, partial=False, ignore_errors=False):
        """Read from stream infile to populate textbuffer"""
        self._text_queue = []
        self._within_body = False
        self._buffer_contents = []
        self._partial = partial
        self._indent = 0

        try:
            for line in infile:
                self.feed(line)

                # yeild items read so far
                for item in self._buffer_contents:
                    yield item
                self._buffer_contents[:] = []
        
            self.close()
            self.flush_text()
        
            # yeild remaining items
            for item in self._buffer_contents:
                yield item
            self._buffer_contents[:] = []
            
        except Exception, e:
            # reraise error if not ignored
            if not ignore_errors:
                raise
        
        
    def flush_text(self):
        if len(self._text_queue) > 0:
            text = "".join(self._text_queue)
            if len(text) > 0:
                self._buffer_contents.append(("text", None, text))
                self._text_queue[:] = []

            
    def queue_text(self, text):
        self._text_queue.append(text)

    def append_buffer_item(self, kind, param):
        self.flush_text()        
        self._buffer_contents.append((kind, None, param))

    def parse_style(self, stylestr):
        """Parse a style attribute"""

        # TODO: this parsing may be too simplistic
        for statement in stylestr.split(";"):
            statement = statement.strip()
            
            tagstr = None
        
            if statement.startswith("font-size"):
                # font size
                size = int("".join(filter(lambda x: x.isdigit(),
                                   statement.split(":")[1])))
                tagstr = "size " + str(size)
                        
            elif statement.startswith("font-family"):
                # font family
                tagstr = "family " + statement.split(":")[1].strip()

                
            elif statement.startswith("text-align"):
                # text justification
                align = statement.split(":")[1].strip()
                
                if align not in self._justify:
                    raise HtmlError("unknown justification '%s'" % align)

                if align == "justify":
                    tagstr = "fill"
                else:
                    tagstr = align

            elif statement.startswith("color"):
                # foreground color
                fg_color = statement.split(":")[1].strip()
                
                if fg_color.startswith("#"):
                    if len(fg_color) == 4:
                        x, a, b, c = fg_color
                        fg_color = x + a + a + b + b+ c + c
                        
                    if len(fg_color) == 7:
                        tagstr = "fg_color " + fg_color

            elif statement.startswith("background-color"):
                # background color
                bg_color = statement.split(":")[1].strip()
                
                if bg_color.startswith("#"):
                    if len(bg_color) == 4:
                        x, a, b, c = bg_color
                        bg_color = x + a + a + b + b+ c + c
                        
                    if len(bg_color) == 7:
                        tagstr = "bg_color " + bg_color

            else:
                # ignore other styles
                pass
        
            if tagstr is not None:
                self.append_buffer_item("beginstr", tagstr)
                self._tag_stack[-1][1].append(tagstr)


    def parse_image(self, attrs):
        """Parse image tag and return image child anchor"""
        
        img = RichTextImage()
        width, height = None, None
            
        for key, value in attrs:
            if key == "src":
                img.set_filename(value)
                    
            elif key == "width":
                try:
                    width = int(value)
                except ValueError, e:
                    # ignore width if we cannot parse it
                    pass
                
            elif key == "height":
                try:
                    height = int(value)
                except ValueError, e:
                    # ignore height if we cannot parse it
                    pass
                
            else:
                # ignore other attributes
                pass
            

        img.scale(width, height)
        return img
        
    
    def handle_starttag(self, htmltag, attrs):
        """Callback for parsing a starting HTML tag"""
        
        self._newline = False

        # start a new tag on htmltag stack
        self._tag_stack.append((htmltag, []))

        if htmltag == "html":
            # ignore html tag
            pass
        
        elif htmltag == "body":
            # note that we are no within the body tag
            self._within_body = True
        
        elif htmltag in self._html2buffer_tag:
            # simple font modifications (b/i/u)
            
            tagstr = self._html2buffer_tag[htmltag]
            self.append_buffer_item("beginstr", tagstr)
            self._tag_stack[-1][1].append(tagstr)

        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    self.parse_style(value)
                else:
                    # ignore other attributes
                    pass
        
        elif htmltag == "div":
            # text justification
            
            for key, value in attrs:
                if key == "style":
                    self.parse_style(value)
                else:
                    # ignore other attributes
                    pass

        elif htmltag == "p":
            # paragraph
            # NOTE: this tag is currently not used by TakeNote, but if pasting
            # text from another HTML source, TakeNote will interpret it as
            # a newline char
            self.queue_text("\n")

        elif htmltag == "ul":
            # indent

            if self._indent > 0:
                self.append_buffer_item("endstr", "indent %d" % self._indent)

            self._indent += 1

            tagstr = "indent %d" % self._indent
            self.append_buffer_item("beginstr", tagstr)
            #self._tag_stack[-1][1].append(tagstr)
            
            #tagstr = "bullet"
            #self.append_buffer_item("beginstr", tagstr)
            #self._tag_stack[-1][1].append(tagstr)

            #self.queue_text(u"\u2022 ")
            
            
            
        elif htmltag == "br":
            # insert newline
            self.queue_text("\n")
            self._newline = True
            
        elif htmltag == "hr":
            # horizontal break
            hr = RichTextHorizontalRule()
            self.append_buffer_item("anchor", (hr, None))
    
        elif htmltag == "img":
            # insert image
            img = self.parse_image(attrs)
            self.append_buffer_item("anchor", (img, None))

        else:
            # ingore other html tags
            pass
        
        


    def handle_endtag(self, htmltag):
        """Callback for parsing a ending HTML tag"""

        if htmltag != "br":
            self._newline = False
            
        if not self._partial:
            if htmltag in ("html", "body") or not self._within_body:
                return

        if len(self._tag_stack) == 0:
            return
        
        htmltag2, tags = self._tag_stack.pop()
        
        # ensure closing tags match opened tags
        while len(self._tag_stack) > 0 and htmltag2 != htmltag:
            html2, tags = self._tag_stack.pop()
            #raise HtmlError("closing tag does not match opening tag")

        for tagstr in tags:
            self.append_buffer_item("endstr", tagstr)

        if htmltag == "ul":
            # indent
            if self._indent > 0:
                self.append_buffer_item("endstr", "indent %d" % self._indent)
                self._indent -= 1
            else:
                # NOTE: this is an error in the HTML input.  More closes than
                # opens
                self._indent = 0

            if self._indent > 0:
                self.append_buffer_item("beginstr", "indent %d" % self._indent)
        
        if htmltag == "p":
            # paragraph tag
            self.queue_text("\n")

    
    
    def handle_data(self, data):
        """Callback for character data"""

        if not self._partial and not self._within_body:
            return
        
        if self._newline:
            data = re.sub("\n[\n ]*", "", data)
            self._newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        self.queue_text(data)

    
    def handle_entityref(self, name):
        if not self._partial and not self._within_body:
            return
        self.queue_text(self._entity2char.get(name, ""))
    
    
    def handle_charref(self, name):
        if not self._partial and not self._within_body:
            return
        self.queue_text(self._charref2char.get(name, ""))



    #================================================
    # Writing HTML
    
    def write(self, buffer_content, tag_table, partial=False):

        if not partial:
            self._out.write(XHTML_HEADER)
        
        for kind, it, param in normalize_tags(
            convert_indent_tags(buffer_content, tag_table),
            is_stable_tag=lambda tag: isinstance(tag, RichTextIndentTag)):
            
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
                        
                    self._out.write("<img src=\"%s\"%s />" % 
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

        if not partial:
            self._out.write(XHTML_FOOTER)
        
    
    def write_tag_begin(self, tag):
        tagname = tag.get_property("name")

        
        if tagname in IGNORE_TAGS:
            pass
        
        elif tagname in self._buffer_tag2html:
            self._out.write("<%s>" % self._buffer_tag2html[tagname])
                    
        elif isinstance(tag, RichTextSizeTag):
            self._out.write('<span style="font-size: %dpt">' % 
                            tag.get_size())

        elif isinstance(tag, RichTextJustifyTag):
            if tagname == "fill":
                text = "justify"
            else:
                text = tagname
            self._out.write('<div style="text-align: %s">' % text)
                
        elif isinstance(tag, RichTextFamilyTag):
            self._out.write('<span style="font-family: %s">' % 
                            tag.get_family())

        elif isinstance(tag, RichTextFGColorTag):
            self._out.write('<span style="color: %s">' % 
                            tagcolor_to_html(
                                tag.get_color()))

        elif isinstance(tag, RichTextBGColorTag):
            self._out.write('<span style="background-color: %s">' % 
                            tagcolor_to_html(
                                tag.get_color()))

        elif isinstance(tag, RichTextIndentTag):
            self._out.write("<ul>")
                
        else:
            raise HtmlError("unknown tag '%s'" % tag.get_property("name"))
                
        
    def write_tag_end(self, tag):
        tagname = tag.get_property("name")
        
        if tagname in self._buffer_tag2html:
            self._out.write("</%s>" % self._buffer_tag2html[tagname])
                            
        elif tagname in self._justify:
            self._out.write("</div>")

        elif isinstance(tag, RichTextIndentTag):
            self._out.write("</ul>")

        else:
            self._out.write("</span>")


def tagcolor_to_html(c):
    assert len(c) == 13
    return c[0] + c[1] + c[2] + c[5] + c[6] + c[9] + c[10]
    


