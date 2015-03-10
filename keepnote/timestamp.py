"""

    KeepNote

    timestamp module

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

import locale
import time

# determine UNIX Epoc (which should be 0, unless the current platform has a
# different definition of epoc)
# Use the epoc date + 1 month (SEC_OFFSET) in order to prevent underflow in
# date due to user's timezone
SEC_OFFSET = 3600 * 24 * 31
EPOC = time.mktime((1970, 2, 1, 0, 0, 0, 3, 1, 0)) - time.timezone - SEC_OFFSET

ENCODING = locale.getdefaultlocale()[1]
if ENCODING is None:
    ENCODING = "utf-8"


"""

0  	tm_year  	(for example, 1993)
1 	tm_mon 	range [1,12]
2 	tm_mday 	range [1,31]
3 	tm_hour 	range [0,23]
4 	tm_min 	range [0,59]
5 	tm_sec 	range [0,61]; see (1) in strftime() description
6 	tm_wday 	range [0,6], Monday is 0
7 	tm_yday 	range [1,366]
8 	tm_isdst 	0, 1 or -1; see below

"""


(TM_YEAR,
 TM_MON,
 TM_MDAY,
 TM_HOUR,
 TM_MIN,
 TM_SEC,
 TM_WDAY,
 TM_YDAY,
 TM_ISDST) = range(9)


"""
%a  Locale's abbreviated weekday name.
%A  Locale's full weekday name.
%b  Locale's abbreviated month name.
%B  Locale's full month name.
%c  Locale's appropriate date and time representation.
%d  Day of the month as a decimal number [01,31].
%H  Hour (24-hour clock) as a decimal number [00,23].
%I  Hour (12-hour clock) as a decimal number [01,12].
%j  Day of the year as a decimal number [001,366].
%m  Month as a decimal number [01,12].
%M  Minute as a decimal number [00,59].
%p  Locale's equivalent of either AM or PM.  (1)
%S  Second as a decimal number [00,61].  (2)
%U  Week number of the year (Sunday as the first day of the week) as a
    decimal number [00,53]. All days in a new year preceding the first
    Sunday are considered to be in week 0.  (3)
%w  Weekday as a decimal number [0(Sunday),6].
%W  Week number of the year (Monday as the first day of the week) as a
    decimal number [00,53]. All days in a new year preceding the first
    Monday are considered to be in week 0.  (3)
%x  Locale's appropriate date representation.
%X  Locale's appropriate time representation.
%y  Year without century as a decimal number [00,99].
%Y  Year with century as a decimal number.
%Z  Time zone name (no characters if no time zone exists).
%%  A literal "%" character.
"""


DEFAULT_TIMESTAMP_FORMATS = {
    "same_day": u"%I:%M %p",
    "same_month": u"%a, %d %I:%M %p",
    "same_year": u"%a, %b %d %I:%M %p",
    "diff_year": u"%a, %b %d, %Y"
}


def get_timestamp():
    """Returns the current timestamp"""
    return int(time.time() - EPOC)


def get_localtime():
    """Returns the local time"""
    return time.localtime()


def get_str_timestamp(timestamp, current=None,
                      formats=DEFAULT_TIMESTAMP_FORMATS):
    """
    Get a string representation of a time stamp

    The string will be abbreviated according to the current time.
    """

    # NOTE: I have written this function to allow unicode formats.
    # The encode/decode functions should allow most unicode formats to
    # to be processed by strftime.  However, a '%' may occur inside a
    # multibyte character.  This is a hack until python issue
    # http://bugs.python.org/issue2782 is resolved.

    if formats is None:
        formats = DEFAULT_TIMESTAMP_FORMATS

    try:
        if current is None:
            current = get_localtime()
        local = time.localtime(timestamp + EPOC)

        if local[TM_YEAR] == current[TM_YEAR]:
            if local[TM_MON] == current[TM_MON]:
                if local[TM_MDAY] == current[TM_MDAY]:
                    return time.strftime(formats["same_day"].encode(ENCODING),
                                         local).decode(ENCODING)
                else:
                    return time.strftime(
                        formats["same_month"].encode(ENCODING),
                        local).decode(ENCODING)
            else:
                return time.strftime(formats["same_year"].encode(ENCODING),
                                     local).decode(ENCODING)
        else:
            return time.strftime(formats["diff_year"].encode(ENCODING),
                                 local).decode(ENCODING)
    except:
        return u"[formatting error]"


def format_timestamp(timestamp, format):
    local = time.localtime(timestamp + EPOC)
    return time.strftime(format.encode(ENCODING), local).decode(ENCODING)


def parse_timestamp(timestamp_str, format):
    # raises error if timestamp cannot be parsed
    tstruct = time.strptime(timestamp_str, format)
    local = time.mktime(tstruct)
    return int(local - EPOC)
