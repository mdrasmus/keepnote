"""

   TagTable and Tags for RichTextBuffer

"""


import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk


# default indentation sizes
MIN_INDENT = 5
INDENT_SIZE = 30
BULLET_PAR_INDENT = 12  # hard-coded for 'Sans 10'
BULLET_FONT_SIZE = 10


def color_to_string(color):
    redstr = hex(color.red)[2:]
    greenstr = hex(color.green)[2:]
    bluestr = hex(color.blue)[2:]

    while len(redstr) < 4:
        redstr = "0" + redstr
    while len(greenstr) < 4:
        greenstr = "0" + greenstr
    while len(bluestr) < 4:
        bluestr = "0" + bluestr

    return "#%s%s%s" % (redstr, greenstr, bluestr)


class RichTextTagTable (gtk.TextTagTable):
    """A tag table for a RichTextBuffer"""
    
    def __init__(self):
        gtk.TextTagTable.__init__(self)

        # modification (mod) font tags
        # All of these can be combined
        self.bold_tag = RichTextModTag("bold", weight=pango.WEIGHT_BOLD)
        self.add(self.bold_tag)
            
        self.italic_tag = RichTextModTag("italic", style=pango.STYLE_ITALIC)
        self.add(self.italic_tag)
            
        self.underline_tag = RichTextModTag("underline",
                                            underline=pango.UNDERLINE_SINGLE)
        self.add(self.underline_tag)
            
        self.no_wrap_tag = RichTextModTag("nowrap", wrap_mode=gtk.WRAP_NONE)
        self.add(self.no_wrap_tag)
        
        self.mod_names = ["bold", "italic", "underline", "nowrap"]


        # Class tags cannot overlap any other tag of the same class
        # example: a piece of text cannot have two colors, two families,
        # two sizes, or two justifications.
        
        # justify tags
        self.left_tag = RichTextJustifyTag("left",
                                           justification=gtk.JUSTIFY_LEFT)
        self.add(self.left_tag)
        self.center_tag = RichTextJustifyTag("center",
                                             justification=gtk.JUSTIFY_CENTER)
        self.add(self.center_tag)
        self.right_tag = RichTextJustifyTag("right",
                                            justification=gtk.JUSTIFY_RIGHT)
        self.add(self.right_tag)
        self.fill_tag = RichTextJustifyTag("fill",
                                           justification=gtk.JUSTIFY_FILL)
        self.add(self.fill_tag)
        
        self.justify2name = {
            gtk.JUSTIFY_LEFT: "left", 
            gtk.JUSTIFY_RIGHT: "right", 
            gtk.JUSTIFY_CENTER: "center", 
            gtk.JUSTIFY_FILL: "fill"
        }
        self.justify_names = ["left", "center", "right", "justify"]

        # class sets
        self.mod_tags = set()
        self.justify_tags = set([self.left_tag, self.center_tag,
                                 self.right_tag, self.fill_tag])
        self.family_tags = set()
        self.size_tags = set()
        self.fg_color_tags = set()
        self.bg_color_tags = set()
        self.indent_tags = set()
        
        self.bullet_tag = RichTextBulletTag()
        self.add(self.bullet_tag)


        self.exclusive_classes = [
            self.justify_tags,
            self.family_tags,
            self.size_tags,
            self.fg_color_tags,
            self.bg_color_tags,
            self.indent_tags]

        self.tag2class = {}

    def get_class(self, tag):
        """Returns the exclusive class of tag,
           or None if not an exclusive tag"""
        return self.tag2class.get(tag, None)
    

    def lookup(self, name):
        """Lookup any tag, create it if needed"""

        # test to see if name is directly in table
        #  modifications and justifications are directly stored
        tag = gtk.TextTagTable.lookup(self, name)
        
        if tag:
            return tag
        
        elif name.startswith("size"):
            # size tag
            return self.lookup_size(int(name.split(" ", 1)[1]))

        elif name.startswith("family"):
            # family tag
            return self.lookup_family(name.split(" ", 1)[1])

        elif name.startswith("fg_color"):
            # foreground color tag
            return self.lookup_fg_color(name.split(" ", 1)[1])

        elif name.startswith("bg_color"):
            # background color tag
            return self.lookup_bg_color(name.split(" ", 1)[1])

        elif name.startswith("indent"):
            return self.lookup_indent(name)

        elif name.startswith("bullet"):
            return self.lookup_bullet(name)

        else:
            raise Exception("unknown tag '%s'" % name)


    def lookup_mod(self, mod):
        """Returns modification tag using name"""
        return gtk.TextTagTable.lookup(self, mod)
    
    
    def lookup_family(self, family):
        """Returns family tag using name"""
        tag = gtk.TextTagTable.lookup(self, "family " + family)        
        if tag is None:
            # TODO: do I need to do error handling here?
            tag = RichTextFamilyTag(family)
            self.add(tag)
            self.family_tags.add(tag)
            self.tag2class[tag] = self.family_tags
        return tag
    
    def lookup_size(self, size):
        """Returns size tag using size"""
        sizename = "size %d" % size
        tag = gtk.TextTagTable.lookup(self, sizename)
        if tag is None:
            tag = RichTextSizeTag(size)
            self.add(tag)
            self.size_tags.add(tag)
            self.tag2class[tag] = self.size_tags
        return tag

    def lookup_justify(self, justify):
        """Returns justify tag"""
        return gtk.TextTagTable.lookup(self, justify)


    def lookup_fg_color(self, color):
        """Returns foreground color tag"""
        colorname = "fg_color " + color
        tag = gtk.TextTagTable.lookup(self, colorname)
        if tag is None:
            tag = RichTextFGColorTag(color)
            self.add(tag)
            self.fg_color_tags.add(tag)
            self.tag2class[tag] = self.fg_color_tags
        return tag


    def lookup_bg_color(self, color):
        """Returns background color tag"""
        colorname = "bg_color " + color
        tag = gtk.TextTagTable.lookup(self, colorname)
        if tag is None:
            tag = RichTextBGColorTag(color)
            self.add(tag)
            self.bg_color_tags.add(tag)
            self.tag2class[tag] = self.bg_color_tags
        return tag


    def lookup_indent(self, indent, par_type="none"):
        """Returns indentation tag"""
        
        if isinstance(indent, str):
            if " " in indent:
                # lookup from string
                tokens = indent.split(" ")
                if len(tokens) == 2:
                    return self.lookup_indent(int(tokens[1]))
                elif len(tokens) == 3:
                    return self.lookup_indent(int(tokens[1]), tokens[2])
                else:
                    raise Exception("bad tag name '%s'" % indent)
            
            else:
                # TODO: is this needed?  maybe html needs it.
                return self.lookup_indent(1)
            
        else:
            # lookup from integer
            tagname = "indent %d %s" % (indent, par_type)
            tag = gtk.TextTagTable.lookup(self, tagname)
            if tag is None:
                tag = RichTextIndentTag(indent, par_type)
                self.add(tag)
                self.indent_tags.add(tag)
                self.tag2class[tag] = self.indent_tags
            return tag


    def lookup_bullet(self, indent):
        """Returns bullet tag"""

        if isinstance(indent, str):
            if " " in indent:
                # lookup from string
                return self.lookup_bullet(int(indent.split(" ", 1)[1]))       
            else:
                return self.lookup_bullet(1)
            
        else:
            # lookup from integer
            tagname = "bullet %d" % indent
            tag = gtk.TextTagTable.lookup(self, tagname)
            if tag is None:
                tag = RichTextBulletTag(indent)
                self.add(tag)
                self.bullet_tags.add(tag)
                self.tag2class[tag] = self.bullet_tags
            return tag
        

class RichTextTag (gtk.TextTag):
    """A TextTag in a RichTextBuffer"""
    def __init__(self, name, **kargs):
        gtk.TextTag.__init__(self, name)

        for key, val in kargs.iteritems():
            self.set_property(key.replace("_", "-"), val)

    def can_be_current(self):
        return True

    def can_be_copied(self):
        return True

    def is_par_related(self):
        return False


class RichTextModTag (RichTextTag):
    """A tag that represents ortholognal font modifications:
       bold, italic, underline, nowrap
    """

    def __init__(self, name, **kargs):
        RichTextTag.__init__(self, name, **kargs)

class RichTextJustifyTag (RichTextTag):
    """A tag that represents ortholognal font modifications:
       bold, italic, underline, nowrap
    """

    def __init__(self, name, **kargs):
        RichTextTag.__init__(self, name, **kargs)


class RichTextFamilyTag (RichTextTag):
    """A tag that represents a font family"""
    def __init__(self, family):
        RichTextTag.__init__(self, "family " + family, family=family)

    def get_family(self):
        return self.get_property("family")    

class RichTextSizeTag (RichTextTag):
    """A tag that represents a font size"""
    def __init__(self, size):
        RichTextTag.__init__(self, "size %d" % size, size_points=size)

    def get_size(self):
        return int(self.get_property("size-points"))
    
class RichTextFGColorTag (RichTextTag):
    """A tag that represents a font foreground color"""
    def __init__(self, color):
        RichTextTag.__init__(self, "fg_color %s" % color,
                             foreground=color)

    def get_color(self):
        return color_to_string(self.get_property("foreground-gdk"))


class RichTextBGColorTag (RichTextTag):
    """A tag that represents a font background color"""
    def __init__(self, color):
        RichTextTag.__init__(self, "bg_color %s" % color,
                             background=color)

    def get_color(self):
        return color_to_string(self.get_property("background-gdk"))


class RichTextIndentTag (RichTextTag):
    """A tag that represents an indentation level"""
    def __init__(self, indent, par_type="none"):

        #if indent <= 0:
        #    print "error"

        if par_type == "bullet":
            par_indent_size = BULLET_PAR_INDENT
            extra_margin = 0
        else:
            # "none"
            par_indent_size = 0
            extra_margin = BULLET_PAR_INDENT

        RichTextTag.__init__(self, "indent %d %s" % (indent, par_type),
                             left_margin=MIN_INDENT + INDENT_SIZE * (indent-1) +
                                         extra_margin,
                             #background="red",
                             indent=-par_indent_size)
            
        self._indent = indent
        self._par_type = par_type

    def get_indent(self):
        return self._indent

    def get_par_indent(self):
        return self._par_type

    def is_par_related(self):
        return True

    

class RichTextBulletTag (RichTextTag):
    """A tag that represents a bullet point"""
    def __init__(self):
        RichTextTag.__init__(self, "bullet",
#                             size_points=BULLET_FONT_SIZE,
                             editable=False)

        # TODO: make sure bullet tag has highest priority so that its font
        # size overrides

    def can_be_current(self):
        return False

    def can_be_copied(self):
        return False

    def is_par_related(self):
        return True
