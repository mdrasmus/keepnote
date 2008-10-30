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


def color_tuple_to_string(color):
    redstr = hex(color[0])[2:]
    greenstr = hex(color[1])[2:]
    bluestr = hex(color[2])[2:]

    while len(redstr) < 4:
        redstr = "0" + redstr
    while len(greenstr) < 4:
        greenstr = "0" + greenstr
    while len(bluestr) < 4:
        bluestr = "0" + bluestr

    return "#%s%s%s" % (redstr, greenstr, bluestr)



class RichTextTagTable (gtk.TextTagTable):
    """A tag table for a RichTextBuffer"""

    # Class Tags:
    # Class tags cannot overlap any other tag of the same class.
    # example: a piece of text cannot have two colors, two families,
    # two sizes, or two justifications.

    
    def __init__(self):
        gtk.TextTagTable.__init__(self)

        self._tag_classes = {}
        self._tag2class = {}

        self.setup()
        

    def setup(self):
        """Setup builtin tags and tag classes"""

        # TODO: maybe move to richtextbase?

        # class sets
        self.new_tag_class("mod", RichTextModTag, exclusive=False)
        self.new_tag_class("justify", RichTextJustifyTag)
        self.new_tag_class("family", RichTextFamilyTag)
        self.new_tag_class("size", RichTextSizeTag)
        self.new_tag_class("fg_color", RichTextFGColorTag)
        self.new_tag_class("bg_color", RichTextBGColorTag)
        self.new_tag_class("indent", RichTextIndentTag)
        self.new_tag_class("bullet", RichTextBulletTag)


        
        # modification (mod) font tags
        # All of these can be combined         
        self.tag_class_add("mod",
            RichTextModTag("bold", weight=pango.WEIGHT_BOLD))
        self.tag_class_add("mod",
            RichTextModTag("italic", style=pango.STYLE_ITALIC))
        self.tag_class_add("mod",
            RichTextModTag("underline",
                           underline=pango.UNDERLINE_SINGLE))
        self.tag_class_add("mod",
            RichTextModTag("nowrap", wrap_mode=gtk.WRAP_NONE))
        

        # justify tags
        self.tag_class_add("justify",
                           RichTextJustifyTag("left",
                                              justification=gtk.JUSTIFY_LEFT))
        self.tag_class_add("justify",
                           RichTextJustifyTag("center",
                                              justification=gtk.JUSTIFY_CENTER))
        self.tag_class_add("justify",
                           RichTextJustifyTag("right",
                                              justification=gtk.JUSTIFY_RIGHT))
        self.tag_class_add("justify",
                           RichTextJustifyTag("fill",
                                              justification=gtk.JUSTIFY_FILL))
        
        
        self.bullet_tag = self.tag_class_add("bullet", RichTextBulletTag())



    def new_tag_class(self, class_name, class_type, exclusive=True):
        """Create a new RichTextTag class for RichTextTagTable"""
        c = RichTextTagClass(class_name, class_type, exclusive)
        self._tag_classes[class_name] = c
        return c

    def get_tag_class(self, class_name):
        """Return the set of tags for a class"""
        return self._tag_classes[class_name]

    def get_tag_class_type(self, class_name):
        """Return the RichTextTag type for a class"""
        return self._tag_classes[class_name].class_type

    def tag_class_add(self, class_name, tag):
        """Add a tag to a tag class"""
        c = self._tag_classes[class_name]
        c.tags.add(tag)
        self.add(tag)
        self._tag2class[tag] = c
        return tag
        

    def get_class_of_tag(self, tag):
        """Returns the exclusive class of tag,
           or None if not an exclusive tag"""
        return self._tag2class.get(tag, None)
    

    def lookup(self, name):
        """Lookup any tag, create it if needed"""

        # test to see if name is directly in table
        #  modifications and justifications are directly stored
        tag = gtk.TextTagTable.lookup(self, name)        
        if tag:
            return tag

        # make tag from scratch
        for tag_class in self._tag_classes.itervalues():
            if tag_class.class_type.is_name(name):
                tag = tag_class.class_type.make_from_name(name)
                self.tag_class_add(tag_class.name, tag)
                return tag
        
        
        raise Exception("unknown tag '%s'" % name)



class RichTextTagClass (object):
    """A class of tags that specify the same attribute
    """

    def __init__(self, name, class_type, exclusive=True):
        """
        name:        name of the class of tags (i.e. "family", "fg_color")
        class_type:  RichTextTag class for all tags in class
        exclusive:   bool for whether tags in class should be mutually exclusive
        """
        
        self.name = name
        self.tags = set()
        self.class_type = class_type
        self.exclusive = exclusive



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

    @classmethod
    def tag_name(cls):
        # NOT implemented
        raise

    @classmethod
    def get_value(cls, tag_name):
        # NOT implemented
        raise

    @classmethod
    def is_name(cls, tag_name):
        return False

    @classmethod
    def make_from_name(cls, tag_name):        
        return cls(cls.get_value(tag_name))


class RichTextModTag (RichTextTag):
    """A tag that represents ortholognal font modifications:
       bold, italic, underline, nowrap
    """

    def __init__(self, name, **kargs):
        RichTextTag.__init__(self, name, **kargs)

    @classmethod
    def tag_name(cls, mod):
        return mod

    @classmethod
    def get_value(cls, tag_name):
        return tag_name



class RichTextJustifyTag (RichTextTag):
    """A tag that represents ortholognal font modifications:
       bold, italic, underline, nowrap
    """

    justify2name = {
        gtk.JUSTIFY_LEFT: "left", 
        gtk.JUSTIFY_RIGHT: "right", 
        gtk.JUSTIFY_CENTER: "center", 
        gtk.JUSTIFY_FILL: "fill"
    }

    justify_names = set(["left", "right", "center", "fill"])

    def __init__(self, name, **kargs):
        RichTextTag.__init__(self, name, **kargs)

    def get_justify(self):
        return self.get_property("name")

    @classmethod
    def tag_name(cls, justify):
        return justify

    @classmethod
    def get_value(cls, tag_name):
        return tag_name

    @classmethod
    def is_name(cls, tag_name):
        return tag_name in cls.justify_names



class RichTextFamilyTag (RichTextTag):
    """A tag that represents a font family"""


    def __init__(self, family):
        RichTextTag.__init__(self, "family " + family, family=family)

    def get_family(self):
        return self.get_property("family")

    @classmethod
    def tag_name(cls, family):
        return "family " + family

    @classmethod
    def get_value(cls, tag_name):
        return tag_name.split(" ", 1)[1]

    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("family ")



class RichTextSizeTag (RichTextTag):
    """A tag that represents a font size"""
    def __init__(self, size):
        RichTextTag.__init__(self, "size %d" % size, size_points=size)

    def get_size(self):
        return int(self.get_property("size-points"))

    @classmethod
    def tag_name(cls, size):
        return "size %d" % size

    @classmethod
    def get_value(cls, tag_name):
        return int(tag_name.split(" ", 1)[1])

    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("size ")

    
class RichTextFGColorTag (RichTextTag):
    """A tag that represents a font foreground color"""
    def __init__(self, color):
        RichTextTag.__init__(self, "fg_color %s" % color,
                             foreground=color)

    def get_color(self):
        return color_to_string(self.get_property("foreground-gdk"))

    @classmethod
    def tag_name(cls, color):
        return "fg_color " + color

    @classmethod
    def get_value(cls, tag_name):
        return tag_name.split(" ", 1)[1]

    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("fg_color ")



class RichTextBGColorTag (RichTextTag):
    """A tag that represents a font background color"""
    def __init__(self, color):
        RichTextTag.__init__(self, "bg_color %s" % color,
                             background=color)

    def get_color(self):
        return color_to_string(self.get_property("background-gdk"))

    @classmethod
    def tag_name(cls, color):
        return "bg_color " + color

    @classmethod
    def get_value(cls, tag_name):
        return tag_name.split(" ", 1)[1]

    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("bg_color ")


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

    @classmethod
    def tag_name(cls, indent, par_type="none"):
        return "indent %d %s" % (indent, par_type)

    @classmethod
    def get_value(cls, tag_name):
        tokens = tag_name.split(" ")

        if len(tokens) == 2:
            return int(tokens[1]), "none"
        elif len(tokens) == 3:
            return int(tokens[1]), tokens[2]
        else:
            raise Exception("bad tag name '%s'" % tag_name)


    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("indent ")

    @classmethod
    def make_from_name(cls, tag_name):        
        return cls(*cls.get_value(tag_name))

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

    @classmethod
    def tag_name(cls):
        return "bullet"

    @classmethod
    def get_value(cls, tag_name):
        return tag_name

    @classmethod
    def is_name(cls, tag_name):
        return tag_name.startswith("bullet")

    @classmethod
    def make_from_name(cls, tag_name):        
        return cls()

    def can_be_current(self):
        return False

    def can_be_copied(self):
        return False

    def is_par_related(self):
        return True

