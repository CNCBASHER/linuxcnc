#!/usr/bin/python2.4
# -*- encoding: utf-8 -*-
#    This is pncconf, a graphical configuration editor for EMC2
#    Chris Morley copyright 2009
#    This is based from stepconf, a graphical configuration editor for emc2
#    Copyright 2007 Jeff Epler <jepler@unpythonic.net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import sys
import os
import pwd
import errno
import time
import md5
import pickle
import shutil
import math
import getopt
import textwrap

import gobject
import gtk
import gtk.glade
import gnome.ui

import xml.dom.minidom

import traceback

# otherwise, on hardy the user is shown spurious "[application] closed
# unexpectedly" messages but denied the ability to actually "report [the]
# problem"
def excepthook(exc_type, exc_obj, exc_tb):
    try:
        w = app.widgets.window1
    except NameError:
        w = None
    lines = traceback.format_exception(exc_type, exc_obj, exc_tb)
    m = gtk.MessageDialog(w,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                _("PNCconf encountered an error.  The following "
                "information may be useful in troubleshooting:\n\n")
                + "".join(lines))
    m.show()
    m.run()
    m.destroy()
sys.excepthook = excepthook

BASE = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), ".."))
LOCALEDIR = os.path.join(BASE, "share", "locale")
import gettext;
#def _(x): return x
gettext.install("emc2", localedir=LOCALEDIR, unicode=True)
gtk.glade.bindtextdomain("emc2", LOCALEDIR)
gtk.glade.textdomain("emc2")

def iceil(x):
    if isinstance(x, (int, long)): return x
    if isinstance(x, basestring): x = float(x)
    return int(math.ceil(x))

datadir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "share", "emc")

wizard = os.path.join(datadir, "emc2-wizard.gif")
if not os.path.isfile(wizard):
    wizard = os.path.join("/etc/emc2/emc2-wizard.gif")
if not os.path.isfile(wizard):
    wizdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
    wizard = os.path.join(wizdir, "emc2-wizard.gif")

distdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "configs", "common")
if not os.path.isdir(distdir):
    distdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "share", "doc", "emc2", "sample-configs", "common")
if not os.path.isdir(distdir):
    distdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "emc2", "sample-configs", "common")
if not os.path.isdir(distdir):
    distdir = "/usr/share/doc/emc2/examples/sample-configs/common"
helpdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..","src/emc/usr_intf/pncconf/pncconf-help")
axisdiagram = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..","src/emc/usr_intf/pncconf/pncconf-help/axisdiagram1.png")
# internalname / displayed name / steptime / step space / direction hold / direction setup
drivertypes = [
    ["gecko201", _("Gecko 201"), 500, 4000, 20000, 1000],
    ["gecko202", _("Gecko 202"), 500, 4500, 20000, 1000],
    ["gecko203v", _("Gecko 203v"), 1000, 2000, 200 , 200],
    ["gecko210", _("Gecko 210"),  500, 4000, 20000, 1000],
    ["gecko212", _("Gecko 212"),  500, 4000, 20000, 1000],
    ["gecko320", _("Gecko 320"),  3500, 500, 200, 200],
    ["gecko540", _("Gecko 540"),  1000, 2000, 200, 200],
    ["l297", _("L297"), 500,  4000, 4000, 1000],
    ["pmdx150", _("PMDX-150"), 1000, 2000, 1000, 1000],
    ["sherline", _("Sherline"), 22000, 22000, 100000, 100000],
    ["xylotex", _("Xylotex 8S-3"), 2000, 1000, 200, 200],
    ["oem750", _("Parker-Compumotor oem750"), 1000, 1000, 1000, 200000],
    ["jvlsmd41", _("JVL-SMD41 or 42"), 500, 500, 2500, 2500],
    ["hobbycnc", _("Hobbycnc Pro Chopper"), 2000, 2000, 2000, 2000],
    ["keling", _("Keling 4030"), 5000, 5000, 20000, 20000],
]

(GPIOI, GPIOO, GPIOD, ENCA, ENCB, ENCI, ENCM, STEPA, STEPB, PWMP, PWMD, PWME, PDMP, PDMD, PDME ) = pintype_names = [
_("GPIO Input"),_("GPIO Output"),_("GPIO O Drain"),
_("HDW Encoder-A"),_("HDW Encoder-B"),_("HDW Encoder-I"),_("HDW Encoder-M"),
_("HDW Step Gen-A"),_("HDW Step Gen-B"),
_("HDW PWM Gen-P"),_("HDW PWM Gen-D"),_("HDW PWM Gen-E"),
_("HDW PDM Gen-P"),_("HDW PDM Gen-D"),_("HDW PDM Gen-E") ]

# boardname, firmwarename,
# max encoders, max pwm gens, 
# max step gens, number of pins per encoder,
# number of pins per step gen, 
# has watchdog, max GPIOI, 
# low frequency rate , hi frequency rate, 
# available connector numbers,  then list of component type and logical number
mesafirmwaredata = [
    ["5i20", "SV12", 12, 12, 0, 3, 0, 1, 72 , 33, 100, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [ENCB,9],[ENCA,9],[ENCB,8],[ENCA,8],[ENCI,9],[ENCI,8],[PWMP,9],[PWMP,8],[PWMD,9],[PWMD,8],[PWME,9],[PWME,8],
                 [ENCB,11],[ENCA,11],[ENCB,10],[ENCA,10],[ENCI,11],[ENCI,10],[PWMP,11],[PWMP,10],[PWMD,11],[PWMD,10],[PWME,11],[PWME,10] ],
    ["5i20", "SVST8_4", 8, 8, 4, 3, 6, 1, 72, 33, 100, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                  [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0] ],
    ["5i20", "SVST2_8", 2, 2, 8, 3, 6, 1, 72, 33, 100, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
        [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                  [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,3],[GPIOI,3],[GPIOI,3],[GPIOI,3],
        [STEPA,4],[STEPB,4],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,5],[STEPB,5],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                  [STEPA,6],[STEPB,6],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,7],[STEPB,7],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0] ],
    ["5i20", "SVST8_4IM2", 8, 8, 4, 4, 2, 1, 72, 33, 100, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [ENCM,0],[ENCM,1],[ENCM,2],[ENCM,3],[ENCM,4],[ENCM,5],[ENCM,6],[ENCM,7],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                 [GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,0],[STEPB,0],[STEPA,1],[STEPB,1],[STEPA,2],[STEPB,2],[STEPA,3],[STEPB,3] ],
    ["5i22", "SV16", 16, 16, 0, 3, 0, 1, 96, 48, 96, [2,3,4,5],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [ENCB,9],[ENCA,9],[ENCB,8],[ENCA,8],[ENCI,9],[ENCI,8],[PWMP,9],[PWMP,8],[PWMD,9],[PWMD,8],[PWME,9],[PWME,8],
                 [ENCB,11],[ENCA,11],[ENCB,10],[ENCA,10],[ENCI,11],[ENCI,10],[PWMP,11],[PWMP,10],[PWMD,11],[PWMD,10],[PWME,11],[PWME,10],
        [ENCB,13],[ENCA,13],[ENCB,12],[ENCA,12],[ENCI,13],[ENCI,12],[PWMP,13],[PWMP,12],[PWMD,13],[PWMD,12],[PWME,13],[PWME,12],
                  [ENCB,15],[ENCA,15],[ENCB,14],[ENCA,14],[ENCI,15],[ENCI,14],[PWMP,15],[PWMP,14],[PWMD,15],[PWMD,14],[PWME,15],[PWME,14] ],
    ["5i22", "SVST8_8", 8, 8, 8, 3, 6, 1, 96, 48, 96, [2,3,4,5],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
       [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,3],[GPIOI,3],[GPIOI,3],[GPIOI,3],
       [STEPA,4],[STEPB,4],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,5],[STEPB,5],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                [STEPA,6],[STEPB,6],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,7],[STEPB,7],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0] ],
    ["5i22", "SVS8_24", 8, 8, 24, 3, 2, 1, 96, 48, 96, [2,3,4,5],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
       [STEPA,0],[STEPB,0],[STEPA,1],[STEPB,1],[STEPA,2],[STEPB,2],[STEPA,3],[STEPB,3],[STEPA,4],[STEPB,4],[STEPA,5],[STEPB,5],
                [STEPA,6],[STEPB,6],[STEPA,7],[STEPB,7],[STEPA,8],[STEPB,8],[STEPA,9],[STEPB,9],[STEPA,10],[STEPB,10],[STEPA,11],[STEPB,11],
       [STEPA,12],[STEPB,12],[STEPA,13],[STEPB,13],[STEPA,14],[STEPB,14],[STEPA,15],[STEPB,15],[STEPA,16],[STEPB,16],[STEPA,17],[STEPB,17],
                [STEPA,18],[STEPB,18],[STEPA,19],[STEPB,19],[STEPA,20],[STEPB,20],[STEPA,21],[STEPB,21],[STEPA,22],[STEPB,22],[STEPA,23],[STEPB,23] ],
    ["5i23", "SV12", 12, 12, 0, 3, 0, 1, 72 , 48, 96, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [ENCB,9],[ENCA,9],[ENCB,8],[ENCA,8],[ENCI,9],[ENCI,8],[PWMP,9],[PWMP,8],[PWMD,9],[PWMD,8],[PWME,9],[PWME,8],
                 [ENCB,11],[ENCA,11],[ENCB,10],[ENCA,10],[ENCI,11],[ENCI,10],[PWMP,11],[PWMP,10],[PWMD,11],[PWMD,10],[PWME,11],[PWME,10] ],
    ["5i23", "SVST8_4", 8, 8, 4, 3, 6, 1, 72, 48, 96, [2,3,4],
        [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                 [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
        [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                 [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6],
        [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                  [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0] ],
    ["5i23", "SVST4_8", 4, 4, 8, 3, 6, 1, 72, 48, 96, [2,3,4],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                 [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
       [STEPA,4],[STEPB,4],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,5],[STEPB,5],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                 [STEPA,6],[STEPB,6],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,7],[STEPB,7],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0] ],
    ["7i43", "SV8", 8, 8, 0, 3, 0, 1, 48, 50, 100, [3,4],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [ENCB,5],[ENCA,5],[ENCB,4],[ENCA,4],[ENCI,5],[ENCI,4],[PWMP,5],[PWMP,4],[PWMD,5],[PWMD,4],[PWME,5],[PWME,4],
                [ENCB,7],[ENCA,7],[ENCB,6],[ENCA,6],[ENCI,7],[ENCI,6],[PWMP,7],[PWMP,6],[PWMD,7],[PWMD,6],[PWME,7],[PWME,6] ],
    ["7i43", "SV4_4", 4, 4, 4, 3, 6, 1, 48, 50, 100, [3,4],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],
                [STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],[GPIOI,0],[GPIOI,0],[STEPA,3],[STEPB,3],[GPIOI,3],[GPIOI,3],[GPIOI,3],[GPIOI,3] ],      
    ["7i43", "SV4_6", 4, 4, 6, 3, 4, 1, 48, 50, 100, [3,4],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [STEPA,0],[STEPB,0],[GPIOI,0],[GPIOI,0],[STEPA,1],[STEPB,1],[GPIOI,0],[GPIOI,0],[STEPA,2],[STEPB,2],[GPIOI,0],[GPIOI,0],
                [STEPA,3],[STEPB,3],[GPIOI,0],[GPIOI,0],[STEPA,4],[STEPB,4],[GPIOI,0],[GPIOI,0],[STEPA,5],[STEPB,5],[GPIOI,0],[GPIOI,0] ],
    ["7i43", "SV4_12", 4, 4, 12, 3, 2, 1, 48, 50, 100, [3,4],
       [ENCB,1],[ENCA,1],[ENCB,0],[ENCA,0],[ENCI,1],[ENCI,0],[PWMP,1],[PWMP,0],[PWMD,1],[PWMD,0],[PWME,1],[PWME,0],
                [ENCB,3],[ENCA,3],[ENCB,2],[ENCA,2],[ENCI,3],[ENCI,2],[PWMP,3],[PWMP,2],[PWMD,3],[PWMD,2],[PWME,3],[PWME,2],
       [STEPA,0],[STEPB,0],[STEPA,1],[STEPB,1],[STEPA,2],[STEPB,2],[STEPA,3],[STEPB,3],[STEPA,4],[STEPB,4],[STEPA,5],[STEPB,5],
                [STEPA,6],[STEPB,6],[STEPA,7],[STEPB,7],[STEPA,8],[STEPB,8],[STEPA,9],[STEPB,9],[STEPA,10],[STEPB,10],[STEPA,11],[STEPB,11] ],
]

mesaboardnames = [ "5i20", "5i22", "5i23", "7i43" ]



(UNUSED_OUTPUT,
ON, CW, CCW, BRAKE,
MIST, FLOOD, ESTOP, AMP,
PUMP, DOUT0, DOUT1, DOUT2, DOUT3) = hal_output_names = [
"unused-output", 
"spindle-enable", "spindle-cw", "spindle-ccw", "spindle-brake",
"coolant-mist", "coolant-flood", "estop-out", "enable",
"charge-pump", "dout-00", "dout-01", "dout-02", "dout-03"
]

(UNUSED_INPUT,
ESTOP_IN, PROBE,
HOME_X, HOME_Y, HOME_Z, HOME_A,
MIN_HOME_X, MIN_HOME_Y, MIN_HOME_Z, MIN_HOME_A,
MAX_HOME_X, MAX_HOME_Y, MAX_HOME_Z, MAX_HOME_A,
BOTH_HOME_X, BOTH_HOME_Y, BOTH_HOME_Z, BOTH_HOME_A,
MIN_X, MIN_Y, MIN_Z, MIN_A,
MAX_X, MAX_Y, MAX_Z, MAX_A,
BOTH_X, BOTH_Y, BOTH_Z, BOTH_A,
ALL_LIMIT, ALL_HOME, DIN0, DIN1, DIN2, DIN3,
JOGA, JOGB, JOGC, SELECT_A, SELECT_B, SELECT_C, SELECT_D,
JOGX_P,JOGX_N,JOGY_P,JOGY_N,JOGZ_P,JOGZ_N,JOGA_P,JOGA_N,
JOGSLCT_P, JOGSLCT_N, SPINDLE_CW, SPINDLE_CCW, SPINDLE_STOP   ) = hal_input_names = ["unused-input",
"estop-ext", "probe-in",
"home-x", "home-y", "home-z", "home-a",
"min-home-x", "min-home-y", "min-home-z", "min-home-a",
"max-home-x", "max-home-y", "max-home-z", "max-home-a",
"both-home-x", "both-home-y", "both-home-z", "both-home-a",
"min-x", "min-y", "min-z", "min-a",
"max-x", "max-y", "max-z", "max-a",
"both-x", "both-y", "both-z", "both-a",
"all-limit", "all-home", "din-00", "din-01", "din-02", "din-03",
"jog-incr-0","jog-incr-1","jog-incr-2",
"joint-select-0","joint-select-1","joint-select-2","joint-select-3",
"jog-x-pos","jog-x-neg","jog-y-pos","jog-y-neg",
"jog-z-pos","jog-z-neg","jog-a-pos","jog-a-neg",
"jog-selected-pos","jog-selected-neg","spindle-manual-cw",
"spindle-manual-ccw","spindle-manual-stop"]

human_output_names = [ _("Unused Output"),
_("Spindle ON"),_("Spindle CW"), _("Spindle CCW"), _("Spindle Brake"),
_("Coolant Mist"), _("Coolant Flood"), _("ESTOP Out"), _("Amplifier Enable"),
_("Charge Pump"),
_("Digital out 0"), _("Digital out 1"), _("Digital out 2"), _("Digital out 3")]

human_input_names = [ _("Unused Input"), _("ESTOP In"), _("Probe In"),
_("X Home"), _("Y Home"), _("Z Home"), _("A Home"),
_("X Minimum Limit + Home"), _("Y Minimum Limit + Home"), _("Z Minimum Limit + Home"), _("A Minimum Limit + Home"),
_("X Maximum Limit + Home"), _("Y Maximum Limit + Home"), _("Z Maximum Limit + Home"), _("A Maximum Limit + Home"),
_("X Both Limit + Home"), _("Y Both Limit + Home"), _("Y Both Limit + Home"), _("A Both Limit + Home"),
_("X Minimum Limit"), _("Y Minimum Limit"), _("Z Minimum Limit"), _("A Minimum Limit"),
_("X Maximum Limit"), _("Y Maximum Limit"), _("Z Maximum Limit"), _("A Maximum Limit"),
_("X Both Limit"), _("Y Both Limit"), _("Z Both Limit"), _("A Both Limit"),
_("All Limits"), _("All Home"),
_("Digital in 0"), _("Digital in 1"), _("Digital in 2"), _("Digital in 3"),
_("Jog incr 0"),_("Jog incr 1"),_("Jog incr 2"),
_("Joint select 0"),_("Joint select 1"),_("Joint select 2"), _("Joint select 3"),
_("Jog X +"),_("Jog X -"),_("Jog Y +"),_("Jog Y -"),_("Jog Z +"),_("Jog Z -"),
_("Jog A +"),_("Jog A -"),_("Jog button selected +"),_("Jog button selected -"),_("Manual Spindle CW"),
_("Manual Spindle CCW"),_("Manual Spindle Stop")]

human_names_multi_jog_buttons = [_("Jog X +"),_("Jog X -"),
_("Jog Y +"),_("Jog Y -"),
_("Jog Z +"),_("Jog Z -"),
_("Jog A +"),_("Jog A -")]

human_names_shared_home = [_("X Minimum Limit + Home"), _("Y Minimum Limit + Home"),
_("Z Minimum Limit + Home"), _("A Minimum Limit + Home"),
_("X Maximum Limit + Home"), _("Y Maximum Limit + Home"),
_("Z Maximum Limit + Home"), _("A Maximum Limit + Home"),
_("X Both Limit + Home"), _("Y Both Limit + Home"),
_("Z Both Limit + Home"), _("A Both Limit + Home")]

human_names_limit_only = [ _("X Minimum Limit"), _("Y Minimum Limit"),
_("Z Minimum Limit"), _("A Minimum Limit"),
_("X Maximum Limit"), _("Y Maximum Limit"),
_("Z Maximum Limit"), _("A Maximum Limit"),
_("X Both Limit"), _("Y Both Limit"),
_("Z Both Limit"), _("A Both Limit"), _("All Limits")]

(UNUSED_PWM,
X_PWM_PULSE, X_PWM_DIR, X_PWM_ENABLE, Y_PWM_PULSE, Y_PWM_DIR, Y_PWM_ENABLE, 
Z_PWM_PULSE, Z_PWM_DIR, Z_PWM_ENABLE, A_PWM_PULSE, A_PWM_DIR, A_PWM_ENABLE, 
SPINDLE_PWM_PULSE, SPINDLE_PWM_DIR, SPINDLE_PWM_ENABLE,   ) = hal_pwm_output_names = ["unused-pwm",
"x-pwm-pulse", "x-pwm-dir", "x-pwm-enable", "y-pwm-pulse", "y-pwm-dir", "y-pwm-enable",
"z-pwm-pulse", "z-pwm-dir", "z-pwm-enable", "a-pwm-pulse", "a-pwm-dir", "a-pwm-enable", 
"s-pwm-pulse", "s-pwm-dir", "s-pwm-enable"]

human_pwm_output_names =[ _("Unused PWM Gen"), 
_("X PWM Pulse Stream"), _("X PWM Direction"), _("X PWM Enable"), 
_("Y PWM Pulse Stream"), _("Y PWM Direction"), _("Y PWM Enable"), 
_("Z PWM Pulse Stream"), _("Z PWM Direction"), _("Z PWM Enable"),
_("A PWM Pulse Stream"), _("A PWM Direction"), _("A PWM Enable"), 
_("Spindle PWM Pulse Stream"), _("Spindle PWM Direction"), _("Spindle PWM Enable"),  ]

(UNUSED_ENCODER, 
X_ENCODER_A, X_ENCODER_B, X_ENCODER_I, X_ENCODER_M,
Y_ENCODER_A, Y_ENCODER_B, Y_ENCODER_I, Y_ENCODER_M,
Z_ENCODER_A, Z_ENCODER_B, Z_ENCODER_I, Z_ENCODER_M, 
A_ENCODER_A, A_ENCODER_B, A_ENCODER_I, A_ENCODER_M, 
SPINDLE_ENCODER_A, SPINDLE_ENCODER_B, SPINDLE_ENCODER_I, SPINDLE_ENCODER_M,
X_MPG_A, X_MPG_B, X_MPG_I, X_MPG_M, Y_MPG_A, Y_MPG_B, Y_MPG_I, Y_MPG_M,
Z_MPG_A, Z_MPG_B, Z_MPG_I, Z_MPG_M, A_MPG_A, A_MPG_B, A_MPG_I,A_MPG_m,
SELECT_MPG_A, SELECT_MPG_B, SELECT_MPG_I, SELECT_MPG_M)  = hal_encoder_input_names = [ "unused-encoder",
"x-encoder-a", "x-encoder-b", "x-encoder-i", "x-encoder-m",
"y-encoder-a", "y-encoder-b", "y-encoder-i", "y-encoder-m",
"z-encoder-a", "z-encoder-b", "z-encoder-i", "z-encoder-m", 
"a-encoder-a", "a-encoder-b", "a-encoder-i", "a-encoder-m",
"s-encoder-a","s-encoder-b","s-encoder-i", "s-encoder-m",
"x-mpg-a","x-mpg-b", "x-mpg-i", "x-mpg-m", "y-mpg-a", "y-mpg-b", "y-mpg-i", "y-mpg-m",
"z-mpg-a","z-mpg-b", "z-mpg-i", "z-mpg-m", "a-mpg-a", "a-mpg-b", "a-mpg-i", "a-mpg-m",
"select-mpg-a", "select-mpg-b", "select-mpg-i", "select-mpg-m"]

human_encoder_input_names = [ _("Unused Encoder"), 
_("X Encoder-A Phase"), _("X Encoder-B Phase"), _("X Encoder-I Phase"), _("X Encoder-M Phase"),
_("Y Encoder-A Phase"), _("Y Encoder-B Phase"), _("Y Encoder-I Phase"), _("Y Encoder-M Phase"), 
_("Z Encoder-A Phase"), _("Z Encoder-B Phase"), _("Z Encoder-I Phase"), _("Z Encoder-M Phase"),
_("A Encoder-A Phase"), _("A Encoder-B Phase"), _("A Encoder-I Phase"), _("A Encoder-M Phase"),
_("Spindle Encoder-A Phase"), _("Spindle  Encoder-B Phase"), _("Spindle Encoder-I Phase"), _("Spindle Encoder-M Phase"), 
_("X Hand Wheel-A Phase"), _("X Hand Wheel-B Phase"), _("X Hand Wheel-I Phase"), _("X Hand Wheel-M Phase"), 
_("Y Hand wheel-A Phase"), _("Y Hand Wheel-B Phase"), _("Y Hand Wheel-I Phase"), _("Y Hand Wheel-M Phase"), 
_("Z Hand Wheel-A Phase"), _("Z Hand Wheel-B Phase"), _("Z Hand Wheel-I Phase"), _("Z Hand Wheel-M Phase"), 
_("A Hand Wheel-A Phase"), _("A Hand Wheel-B Phase"), _("A Hand Wheel-I Phase"), _("A Hand Wheel-M Phase"), 
_("Multi Hand Wheel-A Phase"), _("Multi Hand Wheel-B Phase"), _("Multi Hand Wheel-I Phase"), _("Multi Hand Wheel-M Phase")]

(UNUSED_STEPGEN, 
X_STEPGEN_STEP, X_STEPGEN_DIR, X_STEPGEN_PHC, X_STEPGEN_PHD, X_STEPGEN_PHE, X_STEPGEN_PHF,
Y_STEPGEN_STEP, X_STEPGEN_DIR, X_STEPGEN_PHC, X_STEPGEN_PHD, X_STEPGEN_PHE, X_STEPGEN_PHF,
Z_STEPGEN_STEP, Z_STEPGEN_DIR, Z_STEPGEN_PHC, Z_STEPGEN_PHD, Z_STEPGEN_PHE, Z_STEPGEN_PHF,
A_STEPGEN_STEP, A_STEPGEN_DIR, A_STEPGEN_PHC, A_STEPGEN_PHD, A_STEPGEN_PHE, A_STEPGEN_PHF,
SPINDLE_STEPGEN_STEP, SPINDLE_STEPGEN_DIR, SPINDLE_STEPGEN_PHC, SPINDLE_STEPGEN_PHD, SPINDLE_STEPGEN_PHE, SPINDLE_STEPGEN_PHF) = hal_stepper_names = ["unused-stepgen", 
"x-stepgen-step", "x-stepgen-dir", "x-stepgen-phase-c", "x-stepgen-phase-d", "x-stepgen-phase-e", "x-stepgen-phase-f", 
"y-stepgen-step", "y-stepgen-dir", "y-stepgen-phase-c", "y-stepgen-phase-d", "y-stepgen-phase-e", "y-stepgen-phase-f",
"z-stepgen-step", "z-stepgen-dir", "z-stepgen-phase-c", "z-stepgen-phase-d", "z-stepgen-phase-e", "z-stepgen-phase-f",
"a-stepgen-step", "a-stepgen-dir", "a-stepgen-phase-c", "a-stepgen-phase-d", "a-stepgen-phase-e", "a-stepgen-phase-f",
"s-stepgen-step", "s-stepgen-dir", "s-stepgen-phase-c", "s-stepgen-phase-d", "s-stepgen-phase-e", 
"s-stepgen-phase-f",]

human_stepper_names = [_("Unused StepGen"), _("X StepGen-Step"), _("X StepGen-Direction"), _("X reserved c"), _("X reserved d"), 
_("X reserved e"), _("X reserved f"), _("Y StepGen-Step"), _("Y StepGen-Direction"), _("Y reserved c"), _("Y reserved d"), _("Y reserved e"), 
_("Y reserved f"), _("Z StepGen-Step"), _("Z StepGen-Direction"), _("Z reserved c"), _("Z reserved d"), _("Z reserved e"), _("Z reserved f"), 
_("A StepGen-Step"), _("A StepGen-Direction"), _("A reserved c"), _("A reserved d"), _("A reserved e"), _("A reserved f"), 
_("Spindle StepGen-Step"), _("Spindle StepGen-Direction"), _("Spindle reserved c"), _("Spindle reserved d"), _("Spindle reserved e"), 
_("Spindle reserved f"), ]

def md5sum(filename):
    try:
        f = open(filename, "rb")
    except IOError:
        return None
    else:
        return md5.new(f.read()).hexdigest()

class Widgets:
    def __init__(self, xml):
        self._xml = xml
    def __getattr__(self, attr):
        r = self._xml.get_widget(attr)
        if r is None: raise AttributeError, "No widget %r" % attr
        return r
    def __getitem__(self, attr):
        r = self._xml.get_widget(attr)
        if r is None: raise IndexError, "No widget %r" % attr
        return r

class Intrnl_data:
    def __init__(self):
        self.mesa_configured = False
        self.components_is_prepared = False
        #self.available_axes = []
    def __getitem__(self, item):
        return getattr(self, item)
    def __setitem__(self, item, value):
        return setattr(self, item, value)

class Data:
    def __init__(self):
        pw = pwd.getpwuid(os.getuid())
        # custom signal name lists
        self.halencoderinputsignames = []
        self.halpwmoutputsignames = []
        self.halinputsignames = []
        self.haloutputsignames = []
        self.halsteppersignames = []

        # pncconf default options
        self.createsymlink = 1
        self.createshortcut = 0  

        # basic machine data
        self.help = "help-welcome.txt"
        self.machinename = _("my_EMC_machine")
        self.frontend = 1 # AXIS
        self.axes = 0 # XYZ
        self.available_axes = []
        self.baseperiod = 200000
        self.servoperiod = 1000000
        self.units = 0 # inch
        self.limitsnone = True
        self.limitswitch = False
        self.limitshared = False
        self.homenone = True
        self.homeswitch = False
        self.homeindex = False
        self.homeboth = False
        self.limitstype = 0
        self.homingtype = 0
        self.nojogbuttons = True
        self.singlejogbuttons = False
        self.multijogbuttons = False
        self.jograpidrate = 1.0
        self.guimpg = True    
        self.multimpg = False
        self.singlempg = False
        self.jogscalea = .1
        self.jogscaleb = .01
        self.jogscalec = .001

        

        # GUI frontend defaults
        self.position_offset = 1 # relative
        self.position_feedback = 1 # actual
        self.max_feed_override = 2.0 # percentage
        self.min_spindle_override = .5
        self.max_spindle_override = 1.0
        # These are for AXIS gui only
        self.default_linear_velocity = .25 # units per second
        self.min_linear_velocity = .01
        self.max_linear_velocity = 1.0
        self.default_angular_velocity = .25
        self.min_angular_velocity = .01
        self.max_angular_velocity = 1.0
        self.increments_metric = "5mm 1mm .5mm .1mm .05mm .01mm .005mm"
        self.increments_imperial= ".1in .05in .01in .005in .001in .0005in .0001in"
        self.editor = "gedit"
        self.geometry = "xyz"

        # EMC assorted defults and options
        self.manualtoolchange = True
        self.multimpg = False
        self.require_homing = True
        self.individual_homing = False
        self.restore_joint_position = False
        self.tooloffset_on_w = False
        self.restore_toolnumber = False
        self.raise_z_on_toolchange = False
        self.allow_spindle_on_toolchange = False
        self.customhal = False # include custom hal file
        self.userneededpid = 0

        # pyvcp data
        self.pyvcp = 0 # not included
        self.pyvcpname = "custom.xml"
        self.pyvcphaltype = 0 # no HAL connections specified
        self.pyvcpconnect = 1 # HAL connections allowed

        # classicladder data
        self.classicladder = 0 # not included
        self.digitsin = 15 # default number of pins
        self.digitsout = 15
        self.s32in = 10
        self.s32out = 10
        self.floatsin = 10
        self.floatsout = 10
        self.tempexists = 0 # not present
        self.laddername = "custom.clp"
        self.modbus = 0 # not included
        self.ladderhaltype = 0 # no HAL connections specified
        self.ladderconnect = 1 # HAL connections allowed

        # stepper timing data
        self.drivertype = "other"
        self.steptime = 5000
        self.stepspace = 5000
        self.dirhold = 20000 
        self.dirsetup = 20000
        self.latency = 15000
        self.period = 25000

        # For parallel port 
        self.pp1_direction = 1 # output
        self.ioaddr = "0x378"
        self.ioaddr2 = _("Enter Address")
        self.pp2_direction = 0 # input
        self.ioaddr3 = _("Enter Address")
        self.pp3_direction = 0 # input
        self.number_pports = 0

        for connector in("pp1","pp2","pp3"):
            # initialize parport input / inv pins
            for i in (2,3,4,5,6,7,8,9,10,11,12,13,15):
                pinname ="%sIpin%d"% (connector,i)
                self[pinname] = UNUSED_INPUT
                pinname ="%sIpin%dinv"% (connector,i)
                self[pinname] = False
            # initialize parport output / inv pins
            for i in (1,2,3,4,5,6,7,8,9,14,16,17):
                pinname ="%sOpin%d"% (connector,i)
                self[pinname] = UNUSED_OUTPUT
                pinname ="%sOpin%dinv"% (connector,i)
                self[pinname] = False

        # for mesa cards
        self.mesa5i20 = 1 # number of cards
        self.mesa_currentfirmwaredata = mesafirmwaredata[1]
        self.mesa_boardname = "5i20"
        self.mesa_firmware = "SVST8_4"
        self.mesa_maxgpio = 72
        self.mesa_isawatchdog = 1
        self.mesa_pwm_frequency = 100000
        self.mesa_pdm_frequency = 100000
        self.mesa_watchdog_timeout = 10000000
        self.numof_mesa_encodergens = 4
        self.numof_mesa_pwmgens = 4
        self.numof_mesa_stepgens = 0
        self.numof_mesa_gpio = 48

        connector = 2
        pinname ="m5i20c%dpin"% (connector)
        self[pinname+"0"] = UNUSED_ENCODER
        self[pinname+"0type"] = ENCB
        self[pinname+"1"] = UNUSED_ENCODER
        self[pinname+"1type"] = ENCA
        self[pinname+"2"] = UNUSED_ENCODER
        self[pinname+"2type"] = ENCB
        self[pinname+"3"] = UNUSED_ENCODER
        self[pinname+"3type"] = ENCA
        self[pinname+"4"] = UNUSED_ENCODER
        self[pinname+"4type"] = ENCI
        self[pinname+"5"] = UNUSED_ENCODER
        self[pinname+"5type"] = ENCI
        self[pinname+"6"] = UNUSED_PWM
        self[pinname+"6type"] = PWMP
        self[pinname+"7"] = UNUSED_PWM
        self[pinname+"7type"] = PWMP
        self[pinname+"8"] = UNUSED_PWM
        self[pinname+"8type"] = PWMD
        self[pinname+"9"] = UNUSED_PWM
        self[pinname+"9type"] = PWMD
        self[pinname+"10"] = UNUSED_PWM
        self[pinname+"10type"] = PWME
        self[pinname+"11"] = UNUSED_PWM
        self[pinname+"11type"] = PWME
        self[pinname+"12"] = UNUSED_ENCODER
        self[pinname+"12type"] = ENCB
        self[pinname+"13"] = UNUSED_ENCODER
        self[pinname+"13type"] = ENCA
        self[pinname+"14"] = UNUSED_ENCODER
        self[pinname+"14type"] = ENCB
        self[pinname+"15"] = UNUSED_ENCODER
        self[pinname+"15type"] = ENCA
        self[pinname+"16"] = UNUSED_ENCODER
        self[pinname+"16type"] = ENCI
        self[pinname+"17"] = UNUSED_ENCODER
        self[pinname+"17type"] = ENCI
        self[pinname+"18"] = UNUSED_PWM
        self[pinname+"18type"] = PWMP
        self[pinname+"19"] = UNUSED_PWM
        self[pinname+"19type"] = PWMP
        self[pinname+"20"] = UNUSED_PWM
        self[pinname+"20type"] = PWMD
        self[pinname+"21"] = UNUSED_PWM
        self[pinname+"21type"] = PWMD
        self[pinname+"22"] = UNUSED_PWM
        self[pinname+"22type"] = PWME
        self[pinname+"23"] = UNUSED_PWM
        self[pinname+"23type"] = PWME
        for connector in(3,4,5):
            # This initializes GPIO input pins
            for i in range(0,16):
                pinname ="m5i20c%dpin%d"% (connector,i)
                self[pinname] = UNUSED_INPUT
                pinname ="m5i20c%dpin%dtype"% (connector,i)
                self[pinname] = GPIOI
            # This initializes GPIO output pins
            for i in range(16,24):
                pinname ="m5i20c%dpin%d"% (connector,i)
                self[pinname] = UNUSED_OUTPUT
                pinname ="m5i20c%dpin%dtype"% (connector,i)
                self[pinname] = GPIOO
        for connector in(2,3,4,5):
            # This initializes the mesa inverse pins
            for i in range(0,24):
                pinname ="m5i20c%dpin%dinv"% (connector,i)
                self[pinname] = False

        # halui data
        self.halui = 0 # not included
        # Command list
        for i in range(1,16):
                pinname ="halui_cmd%s"% i
                self[pinname] = ""

        #HAL component command list
        self.loadcompservo = []
        self.addcompservo = []
        self.loadcompbase = []
        self.addcompbase = []

        # axis x data
        self.xdrivertype = "custom"
        self.xsteprev = 200
        self.xmicrostep = 2
        self.xpulleynum = 1
        self.xpulleyden = 1
        self.xleadscrew = 5
        self.xusecomp = 0
        self.xcompfilename = "xcompensation"
        self.xcomptype = 0
        self.xusebacklash = 0
        self.xbacklash = 0
        self.xmaxvel = .0167
        self.xmaxacc = 2
        self.xinvertmotor = 0
        self.xinvertencoder = 0
        self.xoutputscale = 1
        self.xoutputoffset = 0
        self.xmaxoutput = 10
        self.xP = 1.0
        self.xI = 0
        self.xD = 0
        self.xFF0 = 0
        self.xFF1 = 0
        self.xFF2 = 0
        self.xbias = 0
        self.xdeadband = 0
        self.xsteptime = 1000
        self.xstepspace = 1000
        self.xdirhold = 1000
        self.xdirsetup = 1000
        self.xminferror = .0005
        self.xmaxferror = .005
        self.xhomepos = 0
        self.xminlim =  0
        self.xmaxlim =  8
        self.xhomesw =  0
        self.xhomesearchvel = .05
        self.xhomelatchvel = .025
        self.xhomefinalvel = 0
        self.xlatchdir = 0
        self.xsearchdir = 0
        self.xusehomeindex = 1
        self.xhomesequence = 1203
        self.xencodercounts = 4000
        self.xscale = 0

        # axis y data
        self.ydrivertype = "custom"
        self.ysteprev = 200
        self.ymicrostep = 2
        self.ypulleynum = 1
        self.ypulleyden = 1
        self.yleadscrew = 5
        self.yusecomp = 0
        self.ycompfilename = "ycompensation"
        self.ycomptype = 0
        self.yusebacklash = 0
        self.ybacklash = 0
        self.ymaxvel = .0167
        self.ymaxacc = 2
        self.yinvertmotor = 0
        self.yinvertencoder = 0
        self.youtputscale = 1
        self.youtputoffset = 0
        self.ymaxoutput = 10
        self.yP = 1
        self.yI = 0
        self.yD = 0
        self.yFF0 = 0
        self.yFF1 = 0
        self.yFF2 = 0
        self.ybias = 0
        self.ydeadband = 0
        self.ysteptime = 1000
        self.ystepspace = 1000
        self.ydirhold = 1000
        self.ydirsetup = 1000
        self.yminferror = 0.125
        self.ymaxferror = 0.250
        self.yhomepos = 0
        self.yminlim =  0
        self.ymaxlim =  8
        self.yhomesw =  0
        self.yhomesearchvel = .05
        self.yhomelatchvel = .025
        self.yhomefinalvel = 0
        self.ysearchdir = 0
        self.ylatchdir = 0
        self.yusehomeindex = 0
        self.yencodercounts =4000
        self.yscale = 0
   
        # axis z data
        self.zdrivertype = "custom"     
        self.zsteprev = 200
        self.zmicrostep = 2
        self.zpulleynum = 1
        self.zpulleyden = 1
        self.zleadscrew = 5
        self.zusecomp = 0
        self.zcompfilename = "zcompensation"
        self.zcomptype = 0
        self.zusebacklash = 0
        self.zbacklash = 0
        self.zmaxvel = .0167
        self.zmaxacc = 2
        self.zinvertmotor = 0
        self.zinvertencoder = 0
        self.zoutputscale = 1
        self.zoutputoffset = 0
        self.zmaxoutput = 10
        self.zP = 1
        self.zI = 0
        self.zD = 0
        self.zFF0 = 0
        self.zFF1 = 0
        self.zFF2 = 0
        self.zbias = 0
        self.zdeadband = 0
        self.zsteptime = 1000
        self.zstepspace = 1000
        self.zdirhold = 1000
        self.zdirsetup = 1000
        self.zminferror = 0.0005
        self.zmaxferror = 0.005
        self.zhomepos = 0
        self.zminlim = -4
        self.zmaxlim =  0
        self.zhomesw = 0
        self.zhomesearchvel = .05
        self.zhomelatchvel = .025
        self.zhomefinalvel = 0
        self.zsearchdir = 0
        self.zlatchdir = 0
        self.zusehomeindex = 0
        self.zencodercounts = 1000
        self.zscale = 0


        # axis a data
        self.adrivertype = "custom"
        self.asteprev = 200
        self.amicrostep = 2
        self.apulleynum = 1
        self.apulleyden = 1
        self.aleadscrew = 8
        self.ausecomp = 0
        self.acompfilename = "acompensation"
        self.acomptype = 0
        self.ausebacklash = 0
        self.abacklash = 0
        self.amaxvel = 6
        self.amaxacc = 1
        self.ainvertmotor = 0
        self.ainvertencoder = 0
        self.aoutputscale = 1
        self.aoutputoffset = 0
        self.amaxoutput = 10
        self.aP = 1
        self.aI = 0
        self.aD = 0
        self.aFF0 = 0
        self.aFF1 = 0
        self.aFF2 = 0
        self.abias = 0
        self.adeadband = 0
        self.asteptime = 1000
        self.astepspace = 1000
        self.adirhold = 1000
        self.adirsetup = 1000
        self.aminferror = 0.0005
        self.amaxferror = 0.005
        self.ahomepos = 0
        self.aminlim = -9999
        self.amaxlim =  9999
        self.ahomesw =  0
        self.ahomesearchvel = .05
        self.ahomelatchvel = .025
        self.ahomefinalvel = 0
        self.asearchdir = 0
        self.alatchdir = 0
        self.ausehomeindex = 0
        self.aencodercounts = 1000
        self.ascale = 0

        # axis s (spindle) data
        self.sdrivertype = "custom"
        self.ssteprev = 200
        self.smicrostep = 2
        self.spulleynum = 1
        self.spulleyden = 1
        self.sleadscrew = 5
        self.smaxvel = .0167
        self.smaxacc = 2
        self.sinvertmotor = 0
        self.sinvertencoder = 0
        self.sscale = 0
        self.soutputscale = 1
        self.soutputoffset = 0
        self.smaxoutput = 10
        self.sP = 1.0
        self.sI = 0
        self.sD = 0
        self.sFF0 = 0
        self.sFF1 = 0
        self.sFF2 = 0
        self.sbias = 0
        self.sdeadband = 0
        self.ssteptime = 1000
        self.sstepspace = 1000
        self.sdirhold = 1000
        self.sdirsetup = 1000
        self.sencodercounts = 1000
        self.spindlecarrier = 100
        self.spindlecpr = 100
        self.spindlespeed1 = 100
        self.spindlespeed2 = 800
        self.spindlepwm1 = .2
        self.spindlepwm2 = .8
        self.spindlefeedback = 0
        self.spindlecontrol = 0
        self.spindleoutputscale = 1
        self.spindleoutputoffset = 0
        self.spindlemaxoutput = 10
        self.spindlescale = 0
        self.spidcontrol = False

    def load(self, filename, app=None, force=False):
        def str2bool(s):
            return s == 'True'

        converters = {'string': str, 'float': float, 'int': int, 'bool': str2bool, 'eval': eval}

        d = xml.dom.minidom.parse(open(filename, "r"))
        for n in d.getElementsByTagName("property"):
            name = n.getAttribute("name")
            conv = converters[n.getAttribute('type')]
            text = n.getAttribute('value')
            setattr(self, name, conv(text))
        
        # this loads custom signal names created by the user
        for i in  self.halencoderinputsignames:
            hal_encoder_input_names.append(i)
            human_encoder_input_names.append(i)
        for i in  self.halpwmoutputsignames:
            hal_pwm_output_names.append(i)
            human_pwm_output_names.append(i)
        for i in  self.halinputsignames:
            hal_input_names.append(i)
            human_input_names.append(i)
        for i in  self.haloutputsignames:
            hal_output_names.append(i)
            human_output_names.append(i)
        for i in  self.halsteppersignames:
            hal_stepper_names.append(i)
            human_stepper_names.append(i)


        warnings = []
        for f, m in self.md5sums:
            m1 = md5sum(f)
            if m1 and m != m1:
                warnings.append(_("File %r was modified since it was written by PNCconf") % f)
        if not warnings: return

        warnings.append("")
        warnings.append(_("Saving this configuration file will discard configuration changes made outside PNCconf."))
        if app:
            dialog = gtk.MessageDialog(app.widgets.window1,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                     "\n".join(warnings))
            dialog.show_all()
            dialog.run()
            dialog.destroy()
        else:
            for para in warnings:
                for line in textwrap.wrap(para, 78): print line
                print
            print
            if force: return
            response = raw_input(_("Continue? "))
            if response[0] not in _("yY"): raise SystemExit, 1

    def add_md5sum(self, filename, mode="r"):
        self.md5sums.append((filename, md5sum(filename)))

    def write_inifile(self, base):
        filename = os.path.join(base, self.machinename + ".ini")
        file = open(filename, "w")
        print >>file, _("# Generated by PNCconf at %s") % time.asctime()
        print >>file, _("# If you make changes to this file, they will be")
        print >>file, _("# overwritten when you run PNCconf again")
        
        print >>file
        print >>file, "[EMC]"
        print >>file, "MACHINE = %s" % self.machinename
        print >>file, "DEBUG = 0"

        print >>file
        print >>file, "[DISPLAY]"
        if self.frontend == 1:
            print >>file, "DISPLAY = axis"
        elif self.frontend == 2:
            print >>file, "DISPLAY = tkemc"
        else:
            print >>file, "DISPLAY = mini"
        if self.position_offset == 1: temp ="RELATIVE"
        else: temp = "MACHINE"
        print >>file, "POSITION_OFFSET = %s"% temp
        if self.position_feedback == 1: temp ="ACTUAL"
        else: temp = "COMMANDED"
        print >>file, "POSITION_FEEDBACK = %s"% temp
        print >>file, "MAX_FEED_OVERRIDE = %f"% self.max_feed_override
        print >>file, "MAX_SPINDLE_OVERRIDE = %f"% self.max_spindle_override
        print >>file, "MIN_SPINDLE_OVERRIDE = %f"% self.min_spindle_override
        print >>file, "INTRO_GRAPHIC = emc2.gif"
        print >>file, "INTRO_TIME = 5"
        print >>file, "PROGRAM_PREFIX = %s" % \
                                    os.path.expanduser("~/emc2/nc_files")
        if self.pyvcp:
            print >>file, "PYVCP = custompanel.xml"
        # these are for AXIS GUI only
        if self.units:
            print >>file, "INCREMENTS = %s"% self.increments_metric
        else:
            print >>file, "INCREMENTS = %s"% self.increments_imperial
        if self.axes == 2:
            print >>file, "LATHE = 1"
        if self.position_offset:
            temp = "RELATIVE"
        else:
            temp = "MACHINE"
        print >>file, "POSITION_OFFSET = %s"% temp
        if self.position_feedback:
            temp = "ACTUAL"
        else:
            temp = "COMMANDED"
        print >>file, "POSITION_FEEDBACK = %s"% temp
        print >>file, "DEFAULT_LINEAR_VELOCITY = %f"% self.default_linear_velocity
        print >>file, "MAX_LINEAR_VELOCITY = %f"% self.max_linear_velocity
        print >>file, "MIN_LINEAR_VELOCITY = %f"% self.min_linear_velocity
        print >>file, "DEFAULT_ANGULAR_VELOCITY = %f"% self.default_angular_velocity
        print >>file, "MAX_ANGULAR_VELOCITY = %f"% self.max_angular_velocity
        print >>file, "MIN_ANGULAR_VELOCITY = %f"% self.min_angular_velocity
        print >>file, "EDITOR = %s"% self.editor
        print >>file, "GEOMETRY = %s"% self.geometry 

        print >>file
        print >>file, "[FILTER]"
        print >>file, "PROGRAM_EXTENSION = .png,.gif,.jpg Greyscale Depth Image"
        print >>file, "PROGRAM_EXTENSION = .py Python Script"
        print >>file, "png = image-to-gcode"
        print >>file, "gif = image-to-gcode"
        print >>file, "jpg = image-to-gcode"
        print >>file, "py = python"        

        print >>file
        print >>file, "[TASK]"
        print >>file, "TASK = milltask"
        print >>file, "CYCLE_TIME = 0.010"

        print >>file
        print >>file, "[RS274NGC]"
        print >>file, "PARAMETER_FILE = emc.var"

        base_period = self.ideal_period()

        print >>file
        print >>file, "[EMCMOT]"
        print >>file, "EMCMOT = motmod"
        print >>file, "COMM_TIMEOUT = 1.0"
        print >>file, "COMM_WAIT = 0.010"
        print >>file, "BASE_PERIOD = %d" % self.baseperiod
        print >>file, "SERVO_PERIOD = %d" % self.servoperiod
        print >>file
        print >>file, "[HOSTMOT2]"
        print >>file, "DRIVER=hm2_pci"
        print >>file, "BOARD=%s"% self.mesa_boardname
        print >>file, """CONFIG="firmware=hm2-trunk/%s/%s.BIT num_encoders=%d num_pwmgens=%d num_stepgens=%d" """ % (
        self.mesa_boardname, self.mesa_firmware, self.numof_mesa_encodergens, self.numof_mesa_pwmgens, self.numof_mesa_stepgens )
        print >>file
        print >>file, "[HAL]"
        if self.halui:
            print >>file,"HALUI = halui"          
        print >>file, "HALFILE = %s.hal" % self.machinename
        if self.customhal:
            print >>file, "HALFILE = custom.hal"
            print >>file, "POSTGUI_HALFILE = custom_postgui.hal"

        if self.halui:
            print >>file
            print >>file, "[HALUI]"          
            if self.halui == True:
                for i in range(1,16):
                    cmd =self["halui_cmd" + str(i)]
                    if cmd =="": break
                    print >>file,"MDI_COMMAND = %s"% cmd           

        print >>file
        print >>file, "[TRAJ]"
        if self.axes == 1:
            print >>file, "AXES = 4"
            print >>file, "COORDINATES = X Y Z A"
            print >>file, "MAX_ANGULAR_VELOCITY = %.2f" % self.amaxvel
            defvel = min(60, self.amaxvel/10.)
            print >>file, "DEFAULT_ANGULAR_VELOCITY = %.2f" % defvel
        elif self.axes == 0:
            print >>file, "AXES = 3"
            print >>file, "COORDINATES = X Y Z"
        else:
            print >>file, "AXES = 3"
            print >>file, "COORDINATES = X Z"
        if self.units:
            print >>file, "LINEAR_UNITS = mm"
        else:
            print >>file, "LINEAR_UNITS = inch"
        print >>file, "ANGULAR_UNITS = degree"
        print >>file, "CYCLE_TIME = 0.010"
        maxvel = max(self.xmaxvel, self.ymaxvel, self.zmaxvel)        
        hypotvel = (self.xmaxvel**2 + self.ymaxvel**2 + self.zmaxvel**2) **.5
        defvel = min(maxvel, max(.1, maxvel/10.))
        print >>file, "DEFAULT_VELOCITY = %.2f" % defvel
        print >>file, "MAX_LINEAR_VELOCITY = %.2f" % maxvel
        if self.restore_joint_position:
            print >>file, "POSITION_FILE = position.txt"
        if not self.require_homing:
            print >>file, "NO_FORCE_HOMING = 1"
        if self.tooloffset_on_w:
            print >>file, "TLO_IS_ALONG_W = 1"
        #if self.restore_toolnumber:
        #    print >>file, "TLO_IS-ALONG_W = 1"

        print >>file
        print >>file, "[EMCIO]"
        print >>file, "EMCIO = io"
        print >>file, "CYCLE_TIME = 0.100"
        print >>file, "TOOL_TABLE = tool.tbl"
        if self.allow_spindle_on_toolchange:
            print >>file, "TOOLCHANGE_WITH_SPINDLE_ON = 1"
        if self.raise_z_on_toolchange:
            print >>file, "TOOLCHANGE_QUILL_UP = 1"
        

        all_homes = self.home_sig("x") and self.home_sig("z")
        if self.axes != 2: all_homes = all_homes and self.home_sig("y")
        if self.axes == 4: all_homes = all_homes and self.home_sig("a")

        self.write_one_axis(file, 0, "x", "LINEAR", all_homes)
        if self.axes != 2:
            self.write_one_axis(file, 1, "y", "LINEAR", all_homes)
        self.write_one_axis(file, 2, "z", "LINEAR", all_homes)
        if self.axes == 1:
            self.write_one_axis(file, 3, "a", "ANGULAR", all_homes)
        self.write_one_axis(file, 9, "s", "null", all_homes)

        file.close()
        self.add_md5sum(filename)

    def hz(self, axname):
        steprev = getattr(self, axname+"steprev")
        microstep = getattr(self, axname+"microstep")
        pulleynum = getattr(self, axname+"pulleynum")
        pulleyden = getattr(self, axname+"pulleyden")
        leadscrew = getattr(self, axname+"leadscrew")
        maxvel = getattr(self, axname+"maxvel")
        if self.units or axname == 'a': leadscrew = 1./leadscrew
        pps = leadscrew * steprev * microstep * (pulleynum/pulleyden) * maxvel
        return abs(pps)

    def doublestep(self, steptime=None):
        if steptime is None: steptime = self.steptime
        return steptime <= 5000

    def minperiod(self, steptime=None, stepspace=None, latency=None):
        if steptime is None: steptime = self.steptime
        if stepspace is None: stepspace = self.stepspace
        if latency is None: latency = self.latency
        if self.doublestep(steptime):
            return max(latency + steptime + stepspace + 5000, 4*steptime)
        else:
            return latency + max(steptime, stepspace)

    def maxhz(self):
        return 1e9 / self.minperiod()

    def ideal_period(self):
        xhz = self.hz('x')
        yhz = self.hz('y')
        zhz = self.hz('z')
        ahz = self.hz('a')
        if self.axes == 1:
            pps = max(xhz, yhz, zhz, ahz)
        elif self.axes == 0:
            pps = max(xhz, yhz, zhz)
        else:
            pps = max(xhz, zhz)
        base_period = 1e9 / pps
        if base_period > 100000: base_period = 100000
        if base_period < self.minperiod(): base_period = self.minperiod()
        return int(base_period)

    def write_one_axis(self, file, num, letter, type, all_homes):
        order = "1203"
        def get(s): return self[letter + s]       
        pwmgen = self.pwmgen_sig(letter)
        stepgen = self.stepgen_sig(letter)
        print >>file
        print >>file, "#********************"
        if letter == 's':
            print >>file, "# Spindle "
            print >>file, "#********************"
            print >>file, "[SPINDLE_%d]" % num
        else:
            print >>file, "# Axis %s" % letter.upper()
            print >>file, "#********************"
            print >>file, "[AXIS_%d]" % num
            print >>file, "TYPE = %s" % type
            print >>file, "HOME = %s" % get("homepos")
            print >>file, "FERROR = %s"% get("maxferror")
            print >>file, "MIN_FERROR = %s" % get("minferror")
        print >>file, "MAX_VELOCITY = %s" % get("maxvel")
        print >>file, "MAX_ACCELERATION = %s" % get("maxacc")
        if stepgen == "false":
            if (self.spidcontrol == True and letter == 's') or not letter == 's':
                print >>file, "P = %s" % get("P")
                print >>file, "I = %s" % get("I") 
                print >>file, "D = %s" % get("D")
                print >>file, "FF0 = %s" % get("FF0")
                print >>file, "FF1 = %s" % get("FF1")
                print >>file, "FF2 = %s" % get("FF2")
                print >>file, "BIAS = %s"% get("bias") 
                print >>file, "DEADBAND = %s"% get("deadband")
            print >>file, "OUTPUT_SCALE = %s" % get("outputscale")
            print >>file, "OUTPUT_OFFSET = %s" % get("outputoffset")
            print >>file, "MAX_OUTPUT = %s" % get("maxoutput")
            print >>file, "INPUT_SCALE = %s" % get("scale")
        else:
            print >>file, "# these are in nanoseconds"
            print >>file, "DIRSETUP   = %d"% int(get("dirsetup"))
            print >>file, "DIRHOLD    = %d"% int(get("dirhold"))
            print >>file, "STEPLEN    = %d"% int(get("steptime"))          
            print >>file, "STEPSPACE  = %d"% int(get("stepspace"))            
            print >>file, "SCALE = %s"% get("scale") 
        if letter == 's':return  
        if self[letter + "usecomp"]:
            print >>file, "COMP_FILE = %s" % get("compfilename")
            print >>file, "COMP_FILE_TYPE = %s" % get("comptype")
        if self[letter + "usebacklash"]:
            print >>file, "BACKLASH = %s" % get("backlash")
        # emc2 doesn't like having home right on an end of travel,
        # so extend the travel limit by up to .01in or .1mm
        minlim = -abs(get("minlim"))
        maxlim = get("maxlim")
        home = get("homepos")
        if self.units: extend = .001
        else: extend = .01
        minlim = min(minlim, home - extend)
        maxlim = max(maxlim, home + extend)
        print >>file, "MIN_LIMIT = %s" % minlim
        print >>file, "MAX_LIMIT = %s" % maxlim

        thisaxishome = set(("all-home", "home-" + letter, "min-home-" + letter, "max-home-" + letter, "both-home-" + letter))
        ignore = set(("min-home-" + letter, "max-home-" + letter, "both-home-" + letter))
        homes = False
        for i in thisaxishome:
            if not self.findsignal(i) == "false": homes = True
        if homes:
            searchvel = abs(get("homesearchvel"))
            latchvel = abs(get("homelatchvel"))
            if not get("searchdir"):
                 searchvel = -searchvel
                 if not get("latchdir"): 
                    latchvel = -latchvel 
            else:
                if get("latchdir"): 
                    latchvel = -latchvel
            print >>file, "HOME_OFFSET = %f" % get("homesw")
            print >>file, "HOME_SEARCH_VEL = %f" % searchvel
            
                       
            print >>file, "HOME_LATCH_VEL = %f" % latchvel
            print >>file, "HOME_FINAL_VEL = %f" % get("homefinalvel")
            if get("usehomeindex"):useindex = "YES"
            else: useindex = "NO"   
            print >>file, "HOME_USE_INDEX = %s" % useindex
            for i in ignore:
                if not self.findsignal(i) == "false":
                    print >>file, "HOME_IGNORE_LIMITS = YES"
                    break
            if all_homes and not self.individual_homing:
                print >>file, "HOME_SEQUENCE = %s" % order[num]
        else:
            print >>file, "HOME_OFFSET = %s" % get("homepos")

    def home_sig(self, axis):
        thisaxishome = set(("all-home", "home-" + axis, "min-home-" + axis, "max-home-" + axis, "both-home-" + axis))
        for i in thisaxishome:
            if not self.findsignal(i) == "false": return i
        return False

    def min_lim_sig(self, axis):
           thisaxishome = set(("all-limit", "min-" + axis,"min-home-" + axis, "both-" + axis, "both-home-" + axis))
           for i in thisaxishome:
               if not self.findsignal(i) == "false": return i
           return "false"

    def max_lim_sig(self, axis):
           thisaxishome = set(("all-limit", "max-" + axis, "max-home-" + axis, "both-" + axis, "both-home-" + axis))
           for i in thisaxishome:
               if not self.findsignal(i) == "false": return i
           return "false"

    def stepgen_sig(self, axis):
           thisaxisstepgen =  axis + "-stepgen-step" 
           test = self.findsignal(thisaxisstepgen)
           if not test == "false": return test
           else:return "false"

    def encoder_sig(self, axis): 
           thisaxisencoder = axis +"-encoder-a"
           test = self.findsignal(thisaxisencoder)
           if not test == "false": return test
           else:return "false"

    def pwmgen_sig(self, axis):
           thisaxispwmgen =  axis + "-pwm-pulse" 
           test = self.findsignal( thisaxispwmgen)
           if not test == "false": return test
           else:return "false"

    def connect_axis(self, file, num, let):
        axnum = "xyzabcuvws".index(let)
        title = 'AXIS'
        if let == 's':
            title = 'SPINDLE'
        jogwheel = False
        pwmgen = self.pwmgen_sig(let)
        stepgen = self.stepgen_sig(let)
        encoder = self.encoder_sig(let)
        if not self.findsignal(let+"-mpg-a") =="false":
            jogwheel = True
        lat = self.latency
        print >>file, "#*******************"
        print >>file, "#  %s %s" % (title, let.upper())
        print >>file, "#*******************"
        print >>file
         
        if not pwmgen == "false":
            if (self.spidcontrol == True and let == 's') or not let == 's':
                print >>file, "    setp pid.%s.Pgain     [%s_%d]P" % (let, title, axnum)
                print >>file, "    setp pid.%s.Igain     [%s_%d]I" % (let, title, axnum)
                print >>file, "    setp pid.%s.Dgain     [%s_%d]D" % (let, title, axnum)
                print >>file, "    setp pid.%s.bias      [%s_%d]BIAS" % (let, title, axnum)
                print >>file, "    setp pid.%s.FF0       [%s_%d]FF0" % (let, title, axnum)
                print >>file, "    setp pid.%s.FF1       [%s_%d]FF1" % (let, title, axnum)
                print >>file, "    setp pid.%s.FF2       [%s_%d]FF2" % (let, title, axnum)
                print >>file, "    setp pid.%s.deadband  [%s_%d]DEADBAND" % (let, title, axnum)
                print >>file, "    setp pid.%s.maxoutput [%s_%d]MAX_OUTPUT" % (let, title, axnum)
                print >>file
               
            if 'm5i20' in pwmgen:
                pinname = self.make_pinname(pwmgen)
                #TODO do a check to see if encoder sig is from parport or mesa
                print >>file, "# PWM Generator signals/setup"
                print >>file
                print >>file, "    setp "+pinname+".output-type 1" 
                print >>file, "    setp "+pinname+".scale  [%s_%d]OUTPUT_SCALE"% (title, axnum)  
                if let == 's':  
                    
                    x1 = self.spindlepwm1
                    x2 = self.spindlepwm2
                    y1 = self.spindlespeed1
                    y2 = self.spindlespeed2
                    scale = (y2-y1) / (x2-x1)
                    offset = x1 - y1 / scale
                    print >>file
                    
                    #print >>file, "    setp pwmgen.0.pwm-freq %s" % self.spindlecarrier        
                    #print >>file, "    setp pwmgen.0.scale %s" % scale
                    #print >>file, "    setp pwmgen.0.offset %s" % offset
                    #print >>file, "    setp pwmgen.0.dither-pwm true"
                    if self.spidcontrol == True:
                        print >>file, "net spindle-vel-cmd     => pid.%s.command" % (let)
                        print >>file, "net spindle-output     pid.%s.output      => "% (let) + pinname + ".value"
                        print >>file, "net spindle-enable    => pid.%s.enable" % (let) 
                        print >>file, "net spindle-enable    => " + pinname +".enable"
                    else:
                        print >>file, "net spindle-vel-cmd     => " + pinname + ".value"
                        print >>file, "net spindle-enable    => " + pinname +".enable"
                else:
                    print >>file, "net %senable     => pid.%s.enable" % (let, let)                
                    print >>file, "net %soutput     pid.%s.output      => "% (let, let) + pinname + ".value" 
                    print >>file, "net %spos-cmd    axis.%d.motor-pos-cmd     => pid.%s.command" % (let, axnum , let)
                    print >>file, "net %senable     axis.%d.amp-enable-out     => "% (let,axnum) + pinname +".enable"
                print >>file    
        if not stepgen == "false":
            pinname = self.make_pinname(stepgen)
            print >>file, "# Step Gen signals/setup"
            print >>file
            print >>file, "    setp " + pinname + ".dirsetup        [%s_%d]DIRSETUP"% (title, axnum)
            print >>file, "    setp " + pinname + ".dirhold         [%s_%d]DIRHOLD"% (title, axnum)
            print >>file, "    setp " + pinname + ".steplen         [%s_%d]STEPLEN"% (title, axnum)
            print >>file, "    setp " + pinname + ".stepspace       [%s_%d]STEPSPACE"% (title, axnum)
            print >>file, "    setp " + pinname + ".position-scale  [%s_%d]SCALE"% (title, axnum)
            print >>file, "    setp " + pinname + ".maxaccel         0"
            print >>file, "    setp " + pinname + ".maxvel           0"
            print >>file, "    setp " + pinname + ".step_type        0"        
            if let == 's':  
                print >>file, "    setp " + pinname + ".control-type    1"
                print >>file
                print >>file, "net spindle-enable          =>  " + pinname + ".enable" 
                print >>file, "net spindle-vel-cmd-rps     =>  "+ pinname + ".velocity-cmd"
                if encoder == "false":
                    print >>file, "net spindle-vel-fb         <=  "+ pinname + ".velocity-fb"     
            else:
                print >>file
                print >>file, "net %spos-fb     axis.%d.motor-pos-fb   <=  "% (let, axnum) + pinname + ".position-fb"  
                print >>file, "net %spos-cmd    axis.%d.motor-pos-cmd  =>  "% (let, axnum) + pinname + ".position-cmd"
                print >>file, "net %senable     axis.%d.amp-enable-out =>  "% (let, axnum) + pinname + ".enable"  
            print >>file

        if 'm5i20' in encoder:
                pinname = self.make_pinname(encoder)              
                countmode = 0
                # TODO do a check to see if encoder sig is from parport or mesa
                # support for encoder count mode 
                print >>file, "# ---Encoder feedback signals/setup---"
                print >>file             
                print >>file, "    setp "+pinname+".counter-mode %d"% countmode
                print >>file, "    setp "+pinname+".filter 1" 
                print >>file, "    setp "+pinname+".index-invert 0"
                print >>file, "    setp "+pinname+".index-mask 0" 
                print >>file, "    setp "+pinname+".index-mask-invert 0"              
                print >>file, "    setp "+pinname+".scale  [%s_%d]INPUT_SCALE"% (title, axnum)               
                if let == 's':
                    print >>file, "net spindle-vel-fb            <=  " +pinname+".velocity"
                    print >>file, "net spindle-index-enable     <=>  "+ pinname + ".index-enable"       
                    #print >>file, "net spindle-vel-cmd => pid.%d.feedback"% (axnum)                   
                else: 
                    print >>file, "net %spos-fb     <=  "% (let) +pinname+".position"
                    print >>file, "net %spos-fb     =>  pid.%s.feedback"% (let,let) 
                    print >>file, "net %spos-fb     =>  axis.%d.motor-pos-fb" % (let, axnum)  
                print >>file  

        if let =='s':
            print >>file, "# ---setup spindle control signals---" 
            print >>file
            print >>file, "net spindle-vel-cmd-rps    <=  motion.spindle-speed-out-rps"
            print >>file, "net spindle-vel-cmd        <=  motion.spindle-speed-out"
            print >>file, "net spindle-enable         <=  motion.spindle-on"
            #print >>file, "net spindle-on <= motion.spindle-on"
            print >>file, "net spindle-cw             <=  motion.spindle-forward"
            print >>file, "net spindle-ccw            <=  motion.spindle-reverse"
            print >>file, "net spindle-brake          <=  motion.spindle-brake"            

            print >>file, "net spindle-revs           =>  motion.spindle-revs"
            print >>file, "net spindle-atspeed        =>  motion.spindle-at-speed"
            print >>file, "net spindle-vel-fb         =>  motion.spindle-speed-in"
            print >>file, "net spindle-index-enable  <=>  motion.spindle-index-enable"
            return
        
        min_limsig = self.min_lim_sig(let)
        if  min_limsig == "false": min_limsig = "%s-neg-limit" % let
        max_limsig = self.max_lim_sig(let)  
        if  max_limsig == "false": max_limsig = "%s-pos-limit" % let 
        homesig = self.home_sig(let)
        if homesig == "false": homesig = "%s-home-sw" % let
        print >>file, "# ---setup home / limit switch signals---"       
        print >>file       
        print >>file, "net %s     =>  axis.%d.home-sw-in" % (homesig, axnum)       
        print >>file, "net %s     =>  axis.%d.neg-lim-sw-in" % (min_limsig, axnum)       
        print >>file, "net %s     =>  axis.%d.pos-lim-sw-in" % (max_limsig, axnum)
        print >>file
        print >>file, "# ---Setup jogwheel mpg signals---"
        print >>file
        print >>file, "net %s-jog-count     =>  axis.%d.jog-counts" % (let,axnum)
        print >>file, "net %s-jog-enable    =>  axis.%d.jog-enable" % (let,axnum)
        print >>file, "net %s-jog-scale     =>  axis.%d.jog-scale" % (let,axnum)
        print >>file
        if not jogwheel =="false":
            pinname = self.make_pinname(self.findsignal(let+"-mpg-a"))
            if 'HOSTMOT2' in pinname:      
                print >>file, "# connect jogwheel signals to mesa encoder"       
                print >>file, "    setp axis.%d.jog-vel-mode 0" % axnum
                print >>file, "    sets %s-jog-enable true" % let
                print >>file, "    sets %s-jog-scale .010" % let
                print >>file, "    setp %s.filter true" % pinname
                print >>file, "    setp %s.counter-mode true" % pinname
                print >>file, "net %s-jog-count     <=  %s.count"% (let, pinname)
                print >>file
                
                

    def connect_input(self, file):
        print >>file, "# external input signals"
        print >>file
        for q in (2,3,4,5,6,7,8,9,10,11,12,13,15):
            p = self['pp1Ipin%d' % q]
            i = self['pp1Ipin%dinv' % q]
            if p == UNUSED_INPUT: continue
            if i: print >>file, "net %s     <= parport.0.pin-%02d-in-not" % (p, q)
            else: print >>file, "net %s     <= parport.0.pin-%02d-in" % (p, q)
        print >>file
        for connector in (2,3,4):
            board = self.mesa_boardname
            for q in range(0,24):
                p = self['m5i20c%dpin%d' % (connector, q)]
                i = self['m5i20c%dpin%dinv' % (connector, q)]
                t = self['m5i20c%dpin%dtype' % (connector, q)]
                truepinnum = q + ((connector-2)*24)
                # for input pins
                if t == GPIOI:
                    if p == "unused-input":continue 
                    pinname = self.make_pinname(self.findsignal( p )) 
                    print >>file, "# ---",p.upper(),"---"
                    if i: print >>file, "net %s     <=  "% (p)+pinname +".in_not"
                    else: print >>file, "net %s     <=  "% (p)+pinname +".in"
                # for encoder pins
                elif t in (ENCA):
                    if p == "unused-encoder":continue
                    if p in (self.halencoderinputsignames): 
                        pinname = self.make_pinname(self.findsignal( p )) 
                        sig = p.rstrip("-a")
                        print >>file, "# ---",sig.upper(),"---"
                        print >>file, "net %s         <=  "% (sig+"-position")+pinname +".position"   
                        print >>file, "net %s            <=  "% (sig+"-count")+pinname +".count"     
                        print >>file, "net %s         <=  "% (sig+"-velocity")+pinname +".velocity"
                        print >>file, "net %s            <=  "% (sig+"-reset")+pinname +".reset"      
                        print >>file, "net %s     <=  "% (sig+"-index-enable")+pinname +".index-enable"      
                else: continue

    def connect_output(self, file):
        print >>file, "# external output signals"
        print >>file
        for q in (1,2,3,4,5,6,7,8,9,14,16,17):
            p = self['pp1Opin%d' % q]
            i = self['pp1Opin%dinv' % q]
            if p == UNUSED_OUTPUT: continue
            print >>file, "net %s     =>  parport.0.pin-%02d-out" % (p, q)
            if i: print >>file, "    setp parport.0.pin-%02d-out-invert true" % q           
        print >>file
        for connector in (2,3,4):
            for q in range(0,24):
                p = self['m5i20c%dpin%d' % (connector, q)]
                i = self['m5i20c%dpin%dinv' % (connector, q)]
                t = self['m5i20c%dpin%dtype' % (connector, q)]
                truepinnum = q + ((connector-2)*24)
                # for output /open drain pins
                if t in (GPIOO,GPIOD):
                    if p == "unused-output":continue
                    pinname = self.make_pinname(self.findsignal( p ))
                    print >>file, "# ---",p.upper(),"---"
                    print >>file, "    setp "+pinname +".is_output true"
                    if i: print >>file, "    setp "+pinname+".invert_output true"
                    if t == 2: print >>file, "    setp "+pinname+".is_opendrain  true"   
                    print >>file, "net %s     =>  "% (p)+pinname +".out"              
                # for pwm pins
                elif t in (PWMP,PDMP):
                    if p == "unused-pwm":continue
                    if p in (self.halpwmoutputsignames): 
                        pinname = self.make_pinname(self.findsignal( p )) 
                        sig = p.rstrip("-pulse")
                        print >>file, "# ---",sig.upper(),"---"
                        if t == PWMP:
                            print >>file, "    setp "+pinname +".output-type 1"
                        elif t == PDMP:
                            print >>file, "    setp "+pinname +".output-type 3"
                        print >>file, "net %s     <=  "% (sig+"-enable")+pinname +".enable"  
                        print >>file, "net %s      <=  "% (sig+"-value")+pinname +".value" 
                # for stepper pins
                elif t == (STEPA):
                    if p == "unused-stepgen":continue
                    if p in (self.halsteppersignames): 
                        pinname = self.make_pinname(self.findsignal( p )) 
                        sig = p.rstrip("-step")
                        print >>file, "# ---",sig.upper(),"---"
                        print >>file, "net %s           <=  "% (sig+"-enable")+pinname +".enable"  
                        print >>file, "net %s            <=  "% (sig+"-count")+pinname +".counts" 
                        print >>file, "net %s     <=  "% (sig+"-cmd-position")+pinname +".position-cmd"  
                        print >>file, "net %s     <=  "% (sig+"-act-position")+pinname +".position-fb" 
                        print >>file, "net %s         <=  "% (sig+"-velocity")+pinname +".velocity-fb"
                else:continue

    def write_halfile(self, base):
        filename = os.path.join(base, self.machinename + ".hal")
        file = open(filename, "w")
        print >>file, _("# Generated by PNCconf at %s") % time.asctime()
        print >>file, _("# If you make changes to this file, they will be")
        print >>file, _("# overwritten when you run PNCconf again")
        print >>file
        print >>file, "loadrt trivkins"
        print >>file, "loadrt [EMCMOT]EMCMOT base_period_nsec=[EMCMOT]BASE_PERIOD servo_period_nsec=[EMCMOT]SERVO_PERIOD num_joints=[TRAJ]AXES"
        print >>file, "loadrt probe_parport"
        if self.mesa5i20>0:
            print >>file, "loadrt hostmot2"
            print >>file, "loadrt [HOSTMOT2](DRIVER) config=[HOSTMOT2](CONFIG)"
            if self.numof_mesa_pwmgens > 0:
                print >>file, "    setp hm2_[HOSTMOT2](BOARD).0.pwmgen.pwm_frequency %d"% self.mesa_pwm_frequency
                print >>file, "    setp hm2_[HOSTMOT2](BOARD).0.pwmgen.pdm_frequency %d"% self.mesa_pdm_frequency
            print >>file, "    setp hm2_[HOSTMOT2](BOARD).0.watchdog.timeout_ns %d"% self.mesa_watchdog_timeout

        if self.number_pports>0:
            port3name = port2name = port1name = port3dir = port2dir = port1dir = ""
            if self.number_pports>2:
                 port3name = " " + self.ioaddr3
                 if self.pp3_direction:
                    port3dir =" out"
                 else: 
                    port3dir =" in"
            if self.number_pports>1:
                 port2name = " " + self.ioaddr2
                 if self.pp2_direction:
                    port2dir =" out"
                 else: 
                    port2dir =" in"
            port1name = self.ioaddr
            if self.pp1_direction:
               port1dir =" out"
            else: 
               port1dir =" in"
            print >>file, "loadrt hal_parport cfg=\"%s%s%s%s%s%s\"" % (port1name, port1dir, port2name, port2dir, port3name, port3dir)
            if self.doublestep():
                print >>file, "    setp parport.0.reset-time %d" % self.steptime

        spindle_enc = counter = probe = pwm = pump = estop = False 
        enable = spindle_on = spindle_cw = spindle_ccw = False
        mist = flood = brake = False

        if not self.findsignal("spindle-phase-a") == "false":
            spindle_enc = True        
        if not self.findsignal("probe") =="false":
            probe = True
        if not self.findsignal("spindle-pwm") =="false":
            pwm = True
        if not self.findsignal("charge-pump") =="false":
            pump = True
        if not self.findsignal("estop-ext") =="false":
            estop = True
        if not self.findsignal("enable") =="false":
            enable = True
        if not self.findsignal("spindle-enable") =="false":
            spindle_on = True
        if not self.findsignal("spindle-cw") =="false":
            spindle_cw = True
        if not self.findsignal("spindle-ccw") =="false":
            spindle_ccw = True
        if not self.findsignal("coolant-mist") =="false":
            mist = True
        if not self.findsignal("coolant-flood") =="false":
            flood = True
        if not self.findsignal("spindle-brake") =="false":
            brake = True

        #if spindle_enc:
           # print >>file, "loadrt encoder num_chan=1"
        if self.pyvcphaltype == 1 and self.pyvcpconnect == 1:
            print >>file, "loadrt abs count=1"
            if spindle_enc:
               print >>file, "loadrt scale count=1"

        if pump:
            print >>file, "loadrt charge_pump"

       # if pwm:
           # print >>file, "loadrt pwmgen output_type=0"

        if self.classicladder:
            print >>file, "loadrt classicladder_rt numPhysInputs=%d numPhysOutputs=%d numS32in=%d numS32out=%d numFloatIn=%d numFloatOut=%d" %(self.digitsin , self.digitsout , self.s32in, self.s32out, self.floatsin, self.floatsout)
        
        # load user custom components
        for i in self.loadcompbase:
            if i == '': continue
            else:              
                print >>file, i 
        for i in self.loadcompservo:
            if i == '': continue
            else:              
                print >>file, i 

        if self.pyvcp and not self.frontend == 1:
            print >>file, "loadusr -Wn custompanel pyvcp -c custompanel [DISPLAY](PYVCP)"
        print >>file
        if self.number_pports > 0:
            print >>file, "addf parport.0.read base-thread"
        if self.number_pports > 1:
            print >>file, "addf parport.1.read base-thread"
        if self.number_pports > 2:
            print >>file, "addf parport.2.read base-thread"
        #print >>file, "addf stepgen.make-pulses base-thread"
        #if spindle_enc: print >>file, "addf encoder.update-counters base-thread"
        if pump: print >>file, "addf charge-pump base-thread"
        #if pwm: print >>file, "addf pwmgen.make-pulses base-thread"
         
        for i in self.addcompbase:
            if not i == '':
                print >>file, i +" base-thread"

        if self.number_pports > 0:
            print >>file, "addf parport.0.write base-thread"
            if self.doublestep():
                print >>file, "addf parport.0.reset base-thread"
        if self.number_pports > 1:
            print >>file, "addf parport.1.write base-thread"
        if self.number_pports > 2:
            print >>file, "addf parport.2.write base-thread"
        if self.mesa5i20 > 0:
            print >>file, "addf hm2_[HOSTMOT2](BOARD).0.read servo-thread" 
        #print >>file, "addf stepgen.capture-position servo-thread"
        #if spindle_enc: print >>file, "addf encoder.capture-position servo-thread"
        print >>file, "addf motion-command-handler servo-thread"
        print >>file, "addf motion-controller servo-thread"
        temp = 0
        axislet = []
        for i in self.available_axes:
            #if axis needs pid- (has pwm)
            print "looking at available axis : ",i
            if self.findsignal(i+"-encoder-a") == "false": 
                continue 
            if (self.spidcontrol == False and i == 's') :   
                continue
            temp = temp +1 
            axislet.append(i)
            # add axis letter to 'need pid' string
            #if axis is needed
        temp = temp + self.userneededpid
        if temp <> 0 : 
            print >>file, "loadrt pid num_chan=%d"% temp          
            #use 'need pid string' to add calcs and make aliases 
            for j in range(0,temp ):
                print >>file, "addf pid.%d.do-pid-calcs servo-thread"% j
            for axnum,j in enumerate(axislet):
                print >>file, "alias pin    pid.%d.Pgain     pid.%s.Pgain" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.Igain     pid.%s.Igain" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.Dgain     pid.%s.Dgain" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.bias      pid.%s.bias" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.FF0       pid.%s.FF0" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.FF1       pid.%s.FF1" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.FF2       pid.%s.FF2" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.deadband  pid.%s.deadband" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.maxoutput pid.%s.maxoutput" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.enable    pid.%s.enable" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.command   pid.%s.command" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.feedback  pid.%s.feedback" % (axnum + self.userneededpid, j)
                print >>file, "alias pin    pid.%d.output    pid.%s.output" % (axnum + self.userneededpid, j)
                print >>file
        if self.classicladder:
            print >>file,"addf classicladder.0.refresh servo-thread"
        #print >>file, "addf stepgen.update-freq servo-thread"
        if pwm: print >>file, "addf pwmgen.update servo-thread"
        if self.pyvcphaltype == 1 and self.pyvcpconnect == 1:
            print >>file, "addf abs.0 servo-thread"
            if spindle_enc:
               print >>file, "addf scale.0 servo-thread"

        for i in self.addcompservo:
            if not i == '':
                print >>file, i +" servo-thread"

        if self.mesa5i20>0:
            print >>file, "addf hm2_[HOSTMOT2](BOARD).0.write         servo-thread" 
            print >>file, "addf hm2_[HOSTMOT2](BOARD).0.pet_watchdog  servo-thread"
        print >>file
        self.connect_output(file)              
        print >>file
        self.connect_input(file)
        print >>file

        if self.axes == 2:
            self.connect_axis(file, 0, 'x')
            self.connect_axis(file, 1, 'z')
            self.connect_axis(file, 2, 's')
        elif self.axes == 0:
            self.connect_axis(file, 0, 'x')
            self.connect_axis(file, 1, 'y')
            self.connect_axis(file, 2, 'z')
            self.connect_axis(file, 3, 's')
        elif self.axes == 1:
            self.connect_axis(file, 0, 'x')
            self.connect_axis(file, 1, 'y')
            self.connect_axis(file, 2, 'z')
            self.connect_axis(file, 3, 'a')
            self.connect_axis(file, 4, 's')

        print >>file
        print >>file, "#******************************"
        print >>file, _("# connect miscellaneous signals") 
        print >>file, "#******************************"
        print >>file    
        if pump:    
            print >>file, _("#  ---charge pump signals---")
            print >>file, "net estop-out       =>  charge-pump.enable"
            print >>file, "net charge-pump     <=  charge-pump.out"
            print >>file
        print >>file, _("#  ---coolant signals---")
        print >>file
        print >>file, "net coolant-mist      <=  iocontrol.0.coolant-mist"
        print >>file, "net coolant-flood     <=  iocontrol.0.coolant-flood"
        print >>file
        print >>file, _("#  ---probe signal---")
        print >>file
        print >>file, "net probe-in     =>  motion.probe-input"
        print >>file
        if not self.nojogbuttons :
            print >>file, _("# ---jog button signals---")
            print >>file
            print >>file, "net jog-speed            halui.jog-speed "
            print >>file, "     sets jog-speed %f"% self.jograpidrate
            if self.multijogbuttons:
                for axnum,axletter in enumerate(self.available_axes):
                    if not axletter == "s":
                        print >>file, "net jog-%s-pos            halui.jog.%d.plus"% (axletter,axnum)
                        print >>file, "net jog-%s-neg            halui.jog.%d.minus"% (axletter,axnum)
                    if axletter == "s":
                        print >>file, "net spindle-manual-cw     halui.spindle.forward"
                        print >>file, "net spindle-manual-ccw    halui.spindle.reverse"
                        print >>file, "net spindle-manual-stop   halui.spindle.stop"
            else:
                for axnum,axletter in enumerate(self.available_axes):
                    if not axletter == "s":
                        print >>file, "net joint-select-%d         halui.joint.%d.select"% (axnum,axnum)
                print >>file, "net jog-selected-pos     halui.jog.selected.plus"
                print >>file, "net jog-selected-neg     halui.jog.selected.minus"
            print >>file
        if not self.guimpg:
            print >>file, _("#  ---mpg signals---")
            print >>file
            if self.multimpg:
                for axnum,axletter in enumerate(self.available_axes):
                    if not axletter == "s":
                        print >>file, "net joint-select-%d            axis.%d.jog.enable"% (axnum,axnum)
                        print >>file, "net joint-select-%d            axis.%d.jog.counts"% (axnum,axnum)
                        print >>file, "net joint-select-%d            axis.%d.jog.scale"% (axnum,axnum)
                        print >>file, "net joint-select-%d            axis.%d.jog.vel-mode"% (axnum,axnum)

        print >>file, _("#  ---digital in / out signals---")
        print >>file
        for i in range(4):
            dout = "dout-%02d" % i
            if not self.findsignal(dout) =="false":
                print >>file, "net %s     <=  motion.digital-out-%02d" % (dout, i)
        for i in range(4):
            din = "din-%02d" % i
            if not self.findsignal(din) =="false":
                print >>file, "net %s     =>  motion.digital-in-%02d" % (din, i)
        print >>file, _("#  ---estop signals---")
        print >>file
        print >>file, "net estop-out     <=  iocontrol.0.user-enable-out"
        if  self.classicladder and self.ladderhaltype == 1 and self.ladderconnect: # external estop program
            print >>file
            print >>file, _("# **** Setup for external estop ladder program -START ****")
            print >>file
            print >>file, "net estop-out     => classicladder.0.in-00"
            print >>file, "net estop-ext     => classicladder.0.in-01"
            print >>file, "net estop-strobe     classicladder.0.in-02  <=  iocontrol.0.user-request-enable"
            print >>file, "net estop-outcl     classicladder.0.out-00  =>  iocontrol.0.emc-enable-in"
            print >>file
            print >>file, _("# **** Setup for external estop ladder program -END ****")
        elif estop:
            print >>file, "net estop-ext     =>  iocontrol.0.emc-enable-in"
        else:
            print >>file, "net estop-out     =>  iocontrol.0.emc-enable-in"
        if enable:
            print >>file, "net enable        =>  motion.motion-enabled"

        print >>file
        if self.manualtoolchange:
            print >>file, _("#  ---manual tool change signals---")
            print >>file
            print >>file, "loadusr -W hal_manualtoolchange"
            print >>file, "net tool-change-request     iocontrol.0.tool-change       =>  hal_manualtoolchange.change"
            print >>file, "net tool-change-confirmed   iocontrol.0.tool-changed      <=  hal_manualtoolchange.changed"
            print >>file, "net tool-number             iocontrol.0.tool-prep-number  =>  hal_manualtoolchange.number"
            print >>file, "net tool-prepare-loopback   iocontrol.0.tool-prepare      =>  iocontrol.0.tool-prepared"
            print >>file
        else:
            print >>file, _("#  ---toolchange signals for custom tool changer---")
            print >>file
            print >>file, "net tool-number             <=  iocontrol.0.tool-prep-number"
            print >>file, "net tool-change-request     <=  iocontrol.0.tool-change"
            print >>file, "net tool-change-confirmed   =>  iocontrol.0.tool-changed" 
            print >>file, "net tool-prepare-request    <=  iocontrol.0.tool-prepare"
            print >>file, "net tool-prepare-confirmed  =>  iocontrol.0.tool-prepared" 
            print >>file
        if self.classicladder:
            print >>file
            if self.modbus:
                print >>file, _("# Load Classicladder with modbus master included (GUI must run for Modbus)")
                print >>file
                print >>file, "loadusr classicladder --modmaster custom.clp"
                print >>file
            else:
                print >>file, _("# Load Classicladder without GUI (can reload LADDER GUI in AXIS GUI")
                print >>file
                print >>file, "loadusr classicladder --nogui custom.clp"
                print >>file
        if self.pyvcp:
            vcp = os.path.join(base, "custompanel.xml")
            if not os.path.exists(vcp):
                f1 = open(vcp, "w")

                print >>f1, "<?xml version='1.0' encoding='UTF-8'?>"

                print >>f1, "<!-- "
                print >>f1, _("Include your PyVCP panel here.\n")
                print >>f1, "-->"
                print >>f1, "<pyvcp>"
                print >>f1, "</pyvcp>"
        if self.pyvcp or self.customhal:
            custom = os.path.join(base, "custom_postgui.hal")
            if os.path.exists(custom): 
                shutil.copy( custom,os.path.join(base,"postgui_backup.hal") ) 
            f1 = open(custom, "w")
            print >>f1, _("# Include your customized HAL commands here")
            print >>f1, _("""\
# The commands in this file are run after the AXIS GUI (including PyVCP panel) starts""") 
            print >>f1
            if self.pyvcphaltype == 1 and self.pyvcpconnect: # spindle speed/tool # display
                  print >>f1, _("# **** Setup of spindle speed and tool number display using pyvcp -START ****")
                  print >>f1
                  if spindle_enc:
                      print >>f1, _("# **** Use ACTUAL spindle velocity from spindle encoder")
                      print >>f1, _("# **** spindle-velocity is signed so we use absolute compoent to remove sign") 
                      print >>f1, _("# **** ACTUAL velocity is in RPS not RPM so we scale it.")
                      print >>f1
                      print >>f1
                      print >>f1, ("    setp scale.0.gain .01667")
                      print >>f1, ("net spindle-velocity => abs.0.in")
                      print >>f1, ("net absolute-spindle-vel <= abs.0.out => scale.0.in")
                      print >>f1, ("net scaled-spindle-vel <= scale.0.out => pyvcp.spindle-speed")
                  else:
                      print >>f1, _("# **** Use COMMANDED spindle velocity from EMC because no spindle encoder was specified")
                      print >>f1, _("# **** COMANDED velocity is signed so we use absolute component (abs.0) to remove sign")
                      print >>f1
                      print >>f1, ("net spindle-cmd                       =>  abs.0.in")
                      print >>f1, ("net absolute-spindle-vel    abs.0.out =>  pyvcp.spindle-speed")                     
                  print >>f1, ("net tool-number                        => pyvcp.toolnumber")
                  print >>f1
                  print >>f1, _("# **** Setup of spindle speed and tool number display using pyvcp -END ****")
                  print >>f1
            if self.pyvcphaltype == 2 and self.pyvcpconnect: # Hal_UI example
                      print >>f1, _("# **** Setup of pyvcp buttons and MDI commands using HAL_UI and pyvcp - START ****")
                      print >>f1
                      print >>f1, ("net jog-x-pos  <=    pyvcp.jog-x+")
                      print >>f1, ("net jog-x-neg  <=    pyvcp.jog-x-")
                      print >>f1, ("net jog-y-pos  <=    pyvcp.jog-y+")
                      print >>f1, ("net jog-y-neg  <=    pyvcp.jog-y-")
                      print >>f1, ("net jog-z-pos  <=    pyvcp.jog-z+")
                      print >>f1, ("net jog-z-neg  <=    pyvcp.jog-z-")
                      print >>f1, ("net jog-speed  <=    pyvcp.jog-speed")
                      print >>f1, ("net optional-stp-on     pyvcp.ostop-on     =>  halui.program.optional-stop.on")
                      print >>f1, ("net optional-stp-off    pyvcp.ostop-off    =>  halui.program.optional-stop.off")
                      print >>f1, ("net optional-stp-is-on  pyvcp.ostop-is-on  =>  halui.program.optional-stop.is-on")
                      print >>f1, ("net program-pause       pyvcp.pause        =>  halui.program.pause")
                      print >>f1, ("net program-resume      pyvcp.resume       =>  halui.program.resume")
                      print >>f1, ("net program-single-step pyvcp.step         =>  halui.program.step")
                      print >>f1
                      print >>f1, _("# **** The following mdi-comands are specified in the machine named INI file under [HALUI] heading")
                      print >>f1, ("# **** command 00 - rapid to Z 0 ( G0 Z0 )")
                      print >>f1, ("# **** command 01 - rapid to reference point ( G 28 )")
                      print >>f1, ("# **** command 02 - zero X axis in G54 cordinate system")
                      print >>f1, ("# **** command 03 - zero Y axis in G54 cordinate system")
                      print >>f1, ("# **** command 04 - zero Z axis in G54 cordinate system")
                      print >>f1
                      print >>f1, ("net MDI-Z-up            pyvcp.MDI-z_up          =>  halui.mdi-command-00")
                      print >>f1, ("net MDI-reference-pos   pyvcp.MDI-reference     =>  halui.mdi-command-01")
                      print >>f1, ("net MDI-zero_X          pyvcp.MDI-zerox         =>  halui.mdi-command-02")
                      print >>f1, ("net MDI-zero_Y          pyvcp.MDI-zeroy         =>  halui.mdi-command-03")
                      print >>f1, ("net MDI-zero_Z          pyvcp.MDI-zeroz         =>  halui.mdi-command-04")
                      print >>f1, ("net MDI-clear-offset    pyvcp.MDI-clear-offset  =>  halui.mdi-command-05")
                      print >>f1
                      print >>f1, _("# **** Setup of pyvcp buttons and MDI commands using HAL_UI and pyvcp - END ****")

        if self.customhal or self.classicladder or self.halui:
            custom = os.path.join(base, "custom.hal")
            if not os.path.exists(custom):
                f1 = open(custom, "w")
                print >>f1, _("# Include your customized HAL commands here")
                print >>f1, _("# This file will not be overwritten when you run PNCconf again") 
        file.close()
        self.add_md5sum(filename)

    def write_readme(self, base):
        filename = os.path.join(base, "README")
        file = open(filename, "w")
        print >>file, _("Generated by PNCconf at %s") % time.asctime()
        print >>file
        if  self.units == 0: unit = "an imperial"
        else: unit = "a metric"
        if self.frontend == 0: display = "AXIS"
        elif self.frontend == 1: display = "Tkemc"
        elif self.frontend == 2: display = "Mini"
        else: display == "an unknown"
        if self.axes == 0:machinetype ="XYZ"
        elif self.axes == 1:machinetype ="XYZA"
        elif self.axes == 2:machinetype ="XZ-Lathe"
        print >>file, self.machinename,_("configures EMC2 as:")
        print >>file
        print >>file, unit,machinetype,_("type CNC")
        print >>file
        print >>file, display,_("will be used as the frontend display")
        print >>file
        if self.mesa5i20 == True:
            print >>file, "The Mesa", self.mesa_boardname, "hardware I/O card"
            print >>file, "will be loaded with firmware designation:", self.mesa_firmware
            print >>file, "and has", self.mesa_maxgpio, "I/O pins"
        print >>file
        print >>file,_("Mesa 5i20 connector 2 \n")
        for x in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23):
            temp = self["m5i20c2pin%d" % x]
            tempinv = self["m5i20c2pin%dinv" %  x]
            temptype = self["m5i20c2pin%dtype" %  x]
            if tempinv: 
                invmessage = _("-> inverted")
            else: invmessage =""
            print >>file, ("pin# %(pinnum)d (type %(type)s)               "%{ 'type':temptype,'pinnum':x})
            print >>file, ("    connected to signal:'%(data)s'%(mess)s\n" %{'data':temp, 'mess':invmessage}) 
        print >>file
        print >>file,_("Mesa 5i20 connector 3 \n")
        for x in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23):
            temp = self["m5i20c3pin%d" % x]
            tempinv = self["m5i20c3pin%dinv" %  x]
            temptype = self["m5i20c3pin%dtype" %  x]
            if tempinv: 
                invmessage = _("-> inverted")
            else: invmessage =""
            print >>file,("pin# %(pinnum)d (type %(type)s) is connected to signal:'%(data)s'%(mess)s " %{ 
            'type':temptype, 'pinnum':x, 'data':temp,   'mess':invmessage}) 
        print >>file
        print >>file,_("Mesa 5i20 connector 4 \n")
        for x in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23):
            temp = self["m5i20c4pin%d" % x]
            tempinv = self["m5i20c4pin%dinv" %  x]
            temptype = self["m5i20c4pin%dtype" %  x]
            if tempinv: 
                invmessage = _("-> inverted")
            else: invmessage =""
            print >>file,("pin# %(pinnum)d (type %(type)s) is connected to signal:'%(data)s'%(mess)s" %{
            'type':temptype,'pinnum':x, 'data':temp, 'mess':invmessage}) 
        print >>file
        templist = ("pp1","pp2","pp3")
        for j, k in enumerate(templist):
            if self.number_pports < (j+1): break 
            print >>file, _("%(name)s Parport" % { 'name':k})
            for x in (2,3,4,5,6,7,8,9,10,11,12,13,15): 
                temp = self["%sIpin%d" % (k, x)]
                tempinv = self["%sIpin%dinv" % (k, x)]
                if tempinv: 
                    invmessage = _("-> inverted")
                else: invmessage =""
                print >>file,_("pin# %(pinnum)d is connected to input signal:'%(data)s' %(mesag)s" 
                %{ 'pinnum':x,'data':temp,'mesag':invmessage})          
            for x in (1,2,3,4,5,6,7,8,9,14,16,17):  
                temp = self["%sOpin%d" % (k, x)]
                tempinv = self["%sOpin%dinv" % (k, x)]
                if tempinv: 
                    invmessage = _("-> inverted")
                else: invmessage =""
                print >>file,_("pin# %(pinnum)d is connected to output signal:'%(data)s' %(mesag)s" 
                %{ 'pinnum':x,'data':temp,'mesag':invmessage})   
            print >>file 
        file.close()
        self.add_md5sum(filename)

    def copy(self, base, filename):
        dest = os.path.join(base, filename)
        if not os.path.exists(dest):
            shutil.copy(os.path.join(distdir, filename), dest)

    def save(self):
        base = os.path.expanduser("~/emc2/configs/%s" % self.machinename)
        ncfiles = os.path.expanduser("~/emc2/nc_files")
        if not os.path.exists(ncfiles):
            makedirs(ncfiles)
            examples = os.path.join(BASE, "share", "emc", "ncfiles")
            if not os.path.exists(examples):
                examples = os.path.join(BASE, "nc_files")
            if os.path.exists(examples):
                os.symlink(examples, os.path.join(ncfiles, "examples"))
        
        makedirs(base)

        self.md5sums = []
        self.write_readme(base)
        self.write_inifile(base)
        self.write_halfile(base)
        self.copy(base, "tool.tbl")

        filename = "%s.pncconf" % base

        d = xml.dom.minidom.getDOMImplementation().createDocument(
                            None, "stepconf", None)
        e = d.documentElement

        for k, v in sorted(self.__dict__.iteritems()):
            if k.startswith("_"): continue
            n = d.createElement('property')
            e.appendChild(n)

            if isinstance(v, float): n.setAttribute('type', 'float')
            elif isinstance(v, bool): n.setAttribute('type', 'bool')
            elif isinstance(v, int): n.setAttribute('type', 'int')
            elif isinstance(v, list): n.setAttribute('type', 'eval')
            else: n.setAttribute('type', 'string')

            n.setAttribute('name', k)
            n.setAttribute('value', str(v))
        
        d.writexml(open(filename, "wb"), addindent="  ", newl="\n")
        print("%s" % base)

        if self.createsymlink:
            if not os.path.exists(os.path.expanduser("~/Desktop/%s" % self.machinename)):
                os.symlink(base,os.path.expanduser("~/Desktop/%s" % self.machinename))

        if self.createshortcut:
            if os.path.exists(BASE + "/scripts/emc"):
                scriptspath = (BASE + "/scripts/emc")
            else:
                scriptspath ="emc"
            print"%s" % BASE
            print"%s" % scriptspath
            filename = os.path.expanduser("~/Desktop/%s.desktop" % self.machinename)
            file = open(filename, "w")
            print >>file,"[Desktop Entry]"
            print >>file,"Version=1.0"
            print >>file,"Terminal=false"
            print >>file,"Name=" + _("launch %s") % self.machinename
            print >>file,"Exec=%s %s/%s.ini" \
                         % ( scriptspath, base, self.machinename )
            print >>file,"Type=Application"
            print >>file,"Comment=" + _("Desktop Launcher for EMC config made by PNCconf")
            print >>file,"Icon=/etc/emc2/emc2icon.png"
            file.close()

    def __getitem__(self, item):
        return getattr(self, item)
    def __setitem__(self, item, value):
        return setattr(self, item, value)

    # This method returns I/O pin designation (name and number) of a given HAL signalname.
    # It does not check to see if the signalname is in the list more then once.
    def findsignal(self, sig):
        ppinput = {}
        ppoutput = {}
        for i in (1,2,3):
            for s in (2,3,4,5,6,7,8,9,10,11,12,13,15):
                key = self["pp%dIpin%d" %(i,s)]
                ppinput[key] = "pp%dIpin%d" %(i,s) 
            for s in (1,2,3,4,5,6,7,8,9,14,16,17):
                key = self["pp%dOpin%d" %(i,s)]
                ppoutput[key] = "pp%dOpin%d" %(i,s) 

        mesa2=dict([(self["m5i20c2pin%d" %s],"m5i20c2pin%d" %s) for s in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23)])
        mesa3=dict([(self["m5i20c3pin%d" %s],"m5i20c3pin%d" %s) for s in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23)])
        mesa4=dict([(self["m5i20c4pin%d" %s],"m5i20c4pin%d" %s) for s in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23)])
        mesa5=dict([(self["m5i20c5pin%d" %s],"m5i20c5pin%d" %s) for s in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23)])
        try:
            return ppinput[sig]
        except :
            try:
                return ppoutput[sig]
            except :
                try:
                    return mesa2[sig]
                except :
                    try:
                        return mesa3[sig]
                    except :
                        try:
                            return mesa4[sig]
                        except :
                            try:
                                return mesa5[sig]
                            except :
                                return "false"

    # This method takes a signalname data pin (eg m5i20c3pin1)
    # and converts it to a HAL pin names (eg hm2_[HOSTMOT2](BOARD).0.gpio.01)
    # The adj variable is for adjustment of position of pins related to the
    # 'controlling pin' eg encoder-a (controlling pin) encoder-b encoder -I
    # (related pins) 
    def make_pinname(self, pin):
        test = str(pin)       
        if 'm5i20' in test:
            ptype = self[pin+"type"] 
            signalname = self[pin]
            pinnum = int(test[10:])
            connum = int(test[6:7])
            type_name = { GPIOI:"gpio", GPIOO:"gpio", GPIOD:"gpio", ENCA:"encoder", ENCB:"encoder",ENCI:"encoder",ENCM:"encoder", PWMP:"pwmgen", PWMD:"pwmgen", PWME:"pwmgen", PDMP:"pwmgen", PDMD:"pwmgen", PDME:"pwmgen",STEPA:"stepgen", STEPB:"stepgen" }
            try:
                comptype = type_name[ptype]
            except :
                comptype = "false"
            
            #print test,self[pin], ptype, pinnum
            # GPIO pins truenumber can be any number between 0 and 72 for 5i20 ( 96 in 5i22)
            if ptype in(GPIOI,GPIOO,GPIOD):
                truepinnum = int(pinnum)+(int(connum)-2)*24
                return "hm2_[HOSTMOT2](BOARD).0."+comptype+".%03d"% truepinnum 
            
            # Encoder 
            elif ptype in (ENCA,ENCB,ENCI,ENCM):
                adj = 0
                if ptype == ENCB:adj = -1
                if ptype == ENCI:
                    adj = 2
                    if pinnum in(4,16):adj = 3
                if pinnum ==  3 + adj:truepinnum = 0 +((connum-2)*4) 
                elif pinnum == 1 + adj:truepinnum = 1 +((connum-2)*4)
                elif pinnum == 15 + adj:truepinnum = 2 +((connum-2)*4)
                elif pinnum == 13 + adj:truepinnum = 3 +((connum-2)*4) 
                else:print "(encoder) pin number error pinnum = %d"% pinnum
            # PWMGen pins
            elif ptype in (PWMP,PWMD,PWME,PDMP,PDMD,PDME):
                adj = 0
                if signalname.endswith('dir'):adj = 2
                if signalname.endswith('enable'):adj = 4         
                if pinnum == 6 + adj:truepinnum = 0 +((connum-2)*4) 
                elif pinnum == 7 + adj:truepinnum = 1 +((connum-2)*4)
                elif pinnum == 18 + adj:truepinnum = 2 +((connum-2)*4)  
                elif pinnum == 19 + adj:truepinnum = 3 +((connum-2)*4) 
                else:print "(pwm) pin number error pinnum = %d"% pinnum
            # StepGen pins 
            elif ptype in (STEPA,STEPB):
                adj = 0
                if signalname.endswith('dir'):adj = 1
                if signalname.endswith('c'):adj = 2
                if signalname.endswith('d'):adj = 3
                if signalname.endswith('e'):adj = 4
                if signalname.endswith('f'):adj = 5
                if pinnum == 0 + adj:truepinnum = 0 
                elif pinnum == 6 + adj:truepinnum = 1 
                elif pinnum == 12 + adj:truepinnum = 2 
                elif pinnum == 18 + adj:truepinnum = 3
                else:print "(step) pin number error pinnum = %d"% pinnum
            else: print "pintype error"
            return "hm2_[HOSTMOT2](BOARD).0."+comptype+".%02d"% (truepinnum)
        elif 'pp' in test:
            print test
            ending = "-out"
            test = str(pin) 
            print  self[pin]
            pintype = str(test[3:4])
            pinnum = int(test[7:])
            connum = int(test[2:3])-1
            if pintype == 'I': ending = "-in"
            return "parport."+str(connum)+".pin-%02d"%(pinnum)+ending
        else: return "false"

class App:
    fname = 'pncconf.glade'  # XXX search path

    def _getwidget(self, doc, id):
        for i in doc.getElementsByTagName('widget'):
            if i.getAttribute('id') == id: return i

    def make_axispage(self, doc, axisname):
        axispage = self._getwidget(doc, 'xaxis').parentNode.cloneNode(True)
        nextpage = self._getwidget(doc, 'spindle').parentNode
        widget = self._getwidget(axispage, "xaxis")
        for node in widget.childNodes:
            if (node.nodeType == xml.dom.Node.ELEMENT_NODE
                    and node.tagName == "property"
                    and node.getAttribute('name') == "title"):
                node.childNodes[0].data = _("%s Axis Configuration") % axisname.upper()
        for node in axispage.getElementsByTagName("widget"):
            id = node.getAttribute('id')
            if id.startswith("x"):
                node.setAttribute('id', axisname + id[1:])
            else:
                node.setAttribute('id', axisname + id)
        for node in axispage.getElementsByTagName("signal"):
            handler = node.getAttribute('handler')
            node.setAttribute('handler', handler.replace("on_x", "on_" + axisname))
        for node in axispage.getElementsByTagName("property"):
            name = node.getAttribute('name')
            if name == "mnemonic_widget":
                node.childNodes[0].data = axisname + node.childNodes[0].data[1:]
        nextpage.parentNode.insertBefore(axispage, nextpage)

    def make_axismotorpage(self, doc, axisname):
        axispage = self._getwidget(doc, 'xaxismotor').parentNode.cloneNode(True)
        nextpage = self._getwidget(doc, 'xaxis').parentNode
        widget = self._getwidget(axispage, "xaxismotor")
        for node in widget.childNodes:
            if (node.nodeType == xml.dom.Node.ELEMENT_NODE
                    and node.tagName == "property"
                    and node.getAttribute('name') == "title"):
                node.childNodes[0].data = _("%s Axis Motor/Encoder Configuration") % axisname.upper()
        for node in axispage.getElementsByTagName("widget"):
            id = node.getAttribute('id')
            if id.startswith("x"):
                node.setAttribute('id', axisname + id[1:])
            else:
                node.setAttribute('id', axisname + id)
        for node in axispage.getElementsByTagName("signal"):
            handler = node.getAttribute('handler')
            node.setAttribute('handler', handler.replace("on_x", "on_" + axisname))
        for node in axispage.getElementsByTagName("property"):
            name = node.getAttribute('name')
            if name == "mnemonic_widget":
                node.childNodes[0].data = axisname + node.childNodes[0].data[1:]
        nextpage.parentNode.insertBefore(axispage, nextpage)

    def make_pportpage(self, doc, axisname):
        axispage = self._getwidget(doc, 'pp1pport').parentNode.cloneNode(True)
        nextpage = self._getwidget(doc, 'xaxismotor').parentNode
        widget = self._getwidget(axispage, "pp1pport")
        for node in widget.childNodes:
            if (node.nodeType == xml.dom.Node.ELEMENT_NODE
                    and node.tagName == "property"
                    and node.getAttribute('name') == "title"):
                node.childNodes[0].data = _("%s Parallel Port Setup") % axisname
        for node in axispage.getElementsByTagName("widget"):
            id = node.getAttribute('id')
            if id.startswith("pp1"):
                node.setAttribute('id', axisname + id[3:])
            else:
                node.setAttribute('id', axisname + id)
        for node in axispage.getElementsByTagName("signal"):
            handler = node.getAttribute('handler')
            node.setAttribute('handler', handler.replace("on_pp1", "on_" + axisname))
        for node in axispage.getElementsByTagName("property"):
            name = node.getAttribute('name')
            if name == "mnemonic_widget":
                node.childNodes[0].data = axisname + node.childNodes[0].data[1:]
        nextpage.parentNode.insertBefore(axispage, nextpage)

    def __init__(self):
        gnome.init("pncconf", "0.6") 
        glade = xml.dom.minidom.parse(os.path.join(datadir, self.fname))
        self.make_axispage(glade, 'y')
        self.make_axispage(glade, 'z')
        self.make_axispage(glade, 'a')
        self.make_axismotorpage(glade, 'y')
        self.make_axismotorpage(glade, 'z')
        self.make_axismotorpage(glade, 'a')
        self.make_pportpage(glade, 'pp2')
        self.make_pportpage(glade, 'pp3')
        doc = glade.toxml().encode("utf-8")

        self.xml = gtk.glade.xml_new_from_buffer(doc, len(doc), domain="axis")
        self.widgets = Widgets(self.xml)

        self.watermark = gtk.gdk.pixbuf_new_from_file(wizard)
        self.widgets.helppic.set_from_file(axisdiagram)
        self.widgets.openloopdialog.hide()
        self.widgets.druidpagestart1.set_watermark(self.watermark)
        self.widgets.complete.set_watermark(self.watermark)
        self.widgets.druidpagestart1.show()
        self.widgets.complete.show()
        
        self.xml.signal_autoconnect(self)

        self.in_pport_prepare = False
        self.axis_under_test = False
        self.jogminus = self.jogplus = 0
       
        self.intrnldata = Intrnl_data()
        self.data = Data()
         
        tempfile = os.path.join(distdir, "configurable_options/ladder/TEMP.clp")
        if os.path.exists(tempfile):
           os.remove(tempfile) 

    def gtk_main_quit(self, *args):
        gtk.main_quit()

    def on_window1_delete_event(self, *args):
        if self.warning_dialog (_("Quit PNCconfig and discard changes?"),False):
            gtk.main_quit()
            return False
        else:
            return True
    on_druid1_cancel = on_window1_delete_event
    
    def warning_dialog(self,message,is_ok_type):
        if is_ok_type:
           dialog = gtk.MessageDialog(app.widgets.window1,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,message)
           dialog.show_all()
           result = dialog.run()
           dialog.destroy()
           return True
        else:   
            dialog = gtk.MessageDialog(self.widgets.window1,
               gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
               gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,message)
            dialog.show_all()
            result = dialog.run()
            dialog.destroy()
            if result == gtk.RESPONSE_YES:
                return True
            else:
                return False

    def on_helpwindow_delete_event(self, *args):
        self.widgets.helpwindow.hide()
        return True

    def on_druid1_help(self, *args):
        helpfilename = os.path.join(helpdir, "%s"% self.data.help)
        textbuffer = self.widgets.helpview.get_buffer()
        try :
            infile = open(helpfilename, "r")
            if infile:
                string = infile.read()
                infile.close()
                textbuffer.set_text(string)
                self.widgets.helpwindow.set_title(_("Help Pages") )
                self.widgets.helpwindow.show_all()
        except:
            text = _("Help page is unavailable\n")
            self.warning_dialog(text,True)
       

    def on_page_newormodify_prepare(self, *args):
        self.data.help = "help-load.txt"
        self.widgets.createsymlink.set_active(self.data.createsymlink)
        self.widgets.createshortcut.set_active(self.data.createshortcut)

    def on_page_newormodify_next(self, *args):
        if not self.widgets.createconfig.get_active():
            filter = gtk.FileFilter()
            filter.add_pattern("*.pncconf")
            filter.set_name(_("EMC2 'PNCconf' configuration files"))
            dialog = gtk.FileChooserDialog(_("Modify Existing Configuration"),
                self.widgets.window1, gtk.FILE_CHOOSER_ACTION_OPEN,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                 gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_default_response(gtk.RESPONSE_OK)
            dialog.add_filter(filter) 
            dialog.add_shortcut_folder(os.path.expanduser("~/emc2/configs"))
            dialog.set_current_folder(os.path.expanduser("~/emc2/configs"))
            dialog.show_all()
            result = dialog.run()
            if result == gtk.RESPONSE_OK:
                filename = dialog.get_filename()
                dialog.destroy()
                self.data.load(filename, self)
            else:
                dialog.destroy()
                return True
        self.data.createsymlink = self.widgets.createsymlink.get_active()
        self.data.createshortcut = self.widgets.createshortcut.get_active()

    def on_basicinfo_prepare(self, *args):
        self.data.help = "help-basic.txt"
        self.widgets.machinename.set_text(self.data.machinename)
        self.widgets.axes.set_active(self.data.axes)
        self.widgets.units.set_active(self.data.units)
        self.widgets.latency.set_value(self.data.latency)
        self.widgets.baseperiod.set_value(self.data.baseperiod)
        self.widgets.servoperiod.set_value(self.data.servoperiod)
        self.widgets.machinename.grab_focus()
        self.widgets.mesa5i20_checkbutton.set_active(self.data.mesa5i20)
        self.widgets.ioaddr.set_text(self.data.ioaddr)
        self.widgets.ioaddr2.set_text(self.data.ioaddr2) 
        self.widgets.ioaddr3.set_text(self.data.ioaddr3)
        self.widgets.pp1_direction.set_active(self.data.pp1_direction)
        self.widgets.pp2_direction.set_active(self.data.pp2_direction)
        self.widgets.pp3_direction.set_active(self.data.pp3_direction)
        if self.data.number_pports>0:
             self.widgets.pp1_checkbutton.set_active(1)
        else :
             self.widgets.pp1_checkbutton.set_active(0)
        if self.data.number_pports>1:
             self.widgets.pp2_checkbutton.set_active(1)
        if self.data.number_pports>2:
             self.widgets.pp3_checkbutton.set_active(1)
        if self.data.limitsnone :
             self.widgets.limittype_none.set_active(1)
        if self.data.limitswitch :
             self.widgets.limittype_switch.set_active(1)
        if self.data.limitshared :
             self.widgets.limittype_shared.set_active(1)
        if self.data.homenone :
             self.widgets.home_none.set_active(1)
        if self.data.homeindex :
             self.widgets.home_index.set_active(1)
        if self.data.homeswitch :
             self.widgets.home_switch.set_active(1)
        if self.data.homeboth :
             self.widgets.home_both.set_active(1)
        if self.data.manualtoolchange :
            self.widgets.manualtoolchange.set_active(1)
        else:
            self.widgets.tool_custom.set_active(1)
        if self.data.multimpg :
            self.widgets.multimpg.set_active(1)
        else:
            self.widgets.singlempg.set_active(1)
        self.widgets.jograpidrate.set_value(self.data.jograpidrate)
        self.widgets.nojogbuttons.set_active(self.data.nojogbuttons)
        self.widgets.singlejogbuttons.set_active(self.data.singlejogbuttons)
        self.widgets.multijogbuttons.set_active(self.data.multijogbuttons)
        self.widgets.guimpg.set_active(self.data.guimpg)
        self.widgets.singlempg.set_active(self.data.singlempg)
        self.widgets.multimpg.set_active(self.data.multimpg)
        if self.data.units == 0 :
            tempunits = "in"
        else:
            tempunits = "mm"      
        for i in (0,1,2):
            self.widgets["mpgincr"+str(i)].set_text(tempunits)
        self.widgets.jograpidunits.set_text(tempunits+" / min")

    def on_mesa5i20_checkbutton_toggled(self, *args): 
        i = self.widgets.mesa5i20_checkbutton.get_active()   
        self.widgets.nbr5i20.set_sensitive(i)
        
    def on_pp1_checkbutton_toggled(self, *args): 
        i = self.widgets.pp1_checkbutton.get_active()   
        self.widgets.pp1_direction.set_sensitive(i)
        self.widgets.ioaddr.set_sensitive(i)
        if i == 0:
           self.widgets.pp2_checkbutton.set_active(i)
           self.widgets.ioaddr2.set_sensitive(i)
           self.widgets.pp3_checkbutton.set_active(i)
           self.widgets.ioaddr3.set_sensitive(i)

    def on_pp2_checkbutton_toggled(self, *args): 
        i = self.widgets.pp2_checkbutton.get_active()  
        if self.widgets.pp1_checkbutton.get_active() == 0:
          i = 0  
          self.widgets.pp2_checkbutton.set_active(0)
        self.widgets.pp2_direction.set_sensitive(i)
        self.widgets.ioaddr2.set_sensitive(i)
        if i == 0:
           self.widgets.pp3_checkbutton.set_active(i)
           self.widgets.ioaddr3.set_sensitive(i)

    def on_pp3_checkbutton_toggled(self, *args): 
        i = self.widgets.pp3_checkbutton.get_active() 
        if self.widgets.pp2_checkbutton.get_active() == 0:
          i = 0  
          self.widgets.pp3_checkbutton.set_active(0)
        self.widgets.pp3_direction.set_sensitive(i)
        self.widgets.ioaddr3.set_sensitive(i)      

    def on_basicinfo_next(self, *args):

        self.data.machinename = self.widgets.machinename.get_text()
        self.data.axes = self.widgets.axes.get_active()
        if self.data.axes == 0: self.data.available_axes = ['x','y','z','s']
        elif self.data.axes == 1: self.data.available_axes = ['x','y','z','a','s']
        elif self.data.axes == 2: self.data.available_axes = ['x','z','s']
        self.data.units = self.widgets.units.get_active()
        self.data.latency = self.widgets.latency.get_value()
        self.data.baseperiod = self.widgets.baseperiod.get_value()
        self.data.servoperiod = self.widgets.servoperiod.get_value()
        self.data.manualtoolchange = self.widgets.manualtoolchange.get_active()
        self.data.ioaddr = self.widgets.ioaddr.get_text()
        self.data.ioaddr2 = self.widgets.ioaddr2.get_text()
        self.data.ioaddr3 = self.widgets.ioaddr3.get_text()
        self.data.mesa5i20 = self.widgets.mesa5i20_checkbutton.get_active()
        if self.widgets.pp3_checkbutton.get_active() and self.widgets.pp2_checkbutton.get_active():
            self.data.number_pports = 3
        elif self.widgets.pp2_checkbutton.get_active() and self.widgets.pp1_checkbutton.get_active():
            self.data.number_pports = 2
        elif self.widgets.pp1_checkbutton.get_active():
            self.data.number_pports = 1
        else :
            self.data.number_pports = 0
        if self.data.number_pports == 0 and self.data.mesa5i20 == 0 :
           self.warning_dialog(_("You need to designate a parport and/or mesa I/O device before continuing."),True)
           self.widgets.druid1.set_page(self.widgets.basicinfo)
           return True 
        self.data.pp1_direction = self.widgets.pp1_direction.get_active()
        self.data.pp2_direction = self.widgets.pp2_direction.get_active()
        self.data.pp3_direction = self.widgets.pp3_direction.get_active()
        self.data.limitshared = self.widgets.limittype_shared.get_active()
        self.data.limitsnone = self.widgets.limittype_none.get_active()
        self.data.limitswitch = self.widgets.limittype_switch.get_active()
        self.data.limitshared = self.widgets.limittype_shared.get_active()
        self.data.homenone = self.widgets.home_none.get_active()
        self.data.homeindex = self.widgets.home_index.get_active()
        self.data.homeswitch = self.widgets.home_switch.get_active()
        self.data.homeboth = self.widgets.home_both.get_active()
        if self.widgets.multimpg.get_active():
            self.data.multimpg == True            
        else:
            self.data.multimpg == False
        self.data.jograpidrate = self.widgets.jograpidrate.get_value()
        self.data.nojogbuttons = self.widgets.nojogbuttons.get_active()
        self.data.singlejogbuttons = self.widgets.singlejogbuttons.get_active()
        self.data.multijogbuttons = self.widgets.multijogbuttons.get_active()
        if not self.data.nojogbuttons:
            self.data.halui = True
        self.data.guimpg = self.widgets.guimpg.get_active()
        self.data.singlempg = self.widgets.singlempg.get_active()
        self.data.multimpg = self.widgets.multimpg.get_active()

        # connect signals with pin designation data to mesa signal comboboxes and pintype comboboxes
        # record the signal ID numbers so we can block the signals later in the mesa routines
        # have to do it hear manually (instead of autoconnect) because glade doesn't handle added
        # user info (pin number designations) and doesn't record the signal ID numbers
        # none of this is done if mesa is not checked off in pncconf

        if (self.data.mesa5i20 ): 
            for connector in (2,3,4,5):
                for pin in range(0,24):
                    cb = "m5i20c%ipin%i"% (connector,pin)
                    i = "mesasignalhandlerc%ipin%i"% (connector,pin)
                    self.intrnldata[i] = int(self.widgets[cb].connect("changed", self.on_mesa_pin_changed,connector,pin))
                    cb = "m5i20c%ipin%itype"% (connector,pin)
                    i = "mesaptypesignalhandlerc%ipin%i"% (connector,pin)
                    self.intrnldata[i] = int(self.widgets[cb].connect("changed", self.on_mesa_pintype_changed,connector,pin))

            model = self.widgets.mesa_boardname.get_model()
            model.clear()
            for i in mesaboardnames:
                model.append((i,))      
            for search,item in enumerate(mesaboardnames):
                if mesaboardnames[search]  == self.data.mesa_boardname:
                    self.widgets.mesa_boardname.set_active(search)  
            model = self.widgets.mesa_firmware.get_model()
            model.clear()
            for search, item in enumerate(mesafirmwaredata):
                d = mesafirmwaredata[search]
                if not d[0] == self.data.mesa_boardname:continue
                model.append((d[1],))        
            for search,item in enumerate(model):           
                if model[search][0]  == self.data.mesa_firmware:
                    self.widgets.mesa_firmware.set_active(search)   
  
            self.widgets.mesa_pwm_frequency.set_value(self.data.mesa_pwm_frequency)
            self.widgets.mesa_pdm_frequency.set_value(self.data.mesa_pdm_frequency)
            self.widgets.mesa_watchdog_timeout.set_value(self.data.mesa_watchdog_timeout)
            self.widgets.numof_mesa_encodergens.set_value(self.data.numof_mesa_encodergens)
            self.widgets.numof_mesa_pwmgens.set_value(self.data.numof_mesa_pwmgens)
            self.widgets.numof_mesa_stepgens.set_value(self.data.numof_mesa_stepgens)
            self.widgets.numof_mesa_gpio.set_text("%d" % self.data.numof_mesa_gpio)          

    def on_machinename_changed(self, *args):
        self.widgets.confdir.set_text(
            "~/emc2/configs/%s" % self.widgets.machinename.get_text())

    def on_GUI_config_prepare(self, *args):
        self.data.help = "help-gui.txt"
        if self.data.frontend == 1 : self.widgets.GUIAXIS.set_active(True)
        elif self.data.frontend == 2: self.widgets.GUITKEMC.set_active(True)
        else:   self.widgets.GUIMINI.set_active(True)
        self.widgets.pyvcp.set_active(self.data.pyvcp)
        self.on_pyvcp_toggled()
        if  not self.widgets.createconfig.get_active():
           if os.path.exists(os.path.expanduser("~/emc2/configs/%s/custompanel.xml" % self.data.machinename)):
                self.widgets.pyvcpexist.set_active(True)
        self.widgets.default_linear_velocity.set_value( self.data.default_linear_velocity*60)
        self.widgets.max_linear_velocity.set_value( self.data.max_linear_velocity*60)
        self.widgets.min_linear_velocity.set_value( self.data.min_linear_velocity*60)
        self.widgets.default_angular_velocity.set_value( self.data.default_angular_velocity*60)
        self.widgets.max_angular_velocity.set_value( self.data.max_angular_velocity*60)
        self.widgets.min_angular_velocity.set_value( self.data.min_angular_velocity*60)
        self.widgets.editor.set_text(self.data.editor)
        if self.data.units == 0 :
            temp = self.data.increments_imperial
            tempunits = "in / min"
        else:
            temp = self.data.increments_metric
            tempunits = "mm / min"
        self.widgets.increments.set_text(temp)
        for i in (0,1,2):
            self.widgets["velunits"+str(i)].set_text(tempunits)
        self.widgets.position_offset.set_active(self.data.position_offset)
        self.widgets.position_feedback.set_active(self.data.position_feedback)
        self.widgets.geometry.set_text(self.data.geometry)
        self.widgets.pyvcpconnect.set_active(self.data.pyvcpconnect)
        self.widgets.require_homing.set_active(self.data.require_homing)
        self.widgets.individual_homing.set_active(self.data.individual_homing)
        self.widgets.restore_joint_position.set_active(self.data.restore_joint_position) 
        self.widgets.tooloffset_on_w.set_active(self.data.tooloffset_on_w) 
        self.widgets.restore_toolnumber.set_active(self.data.restore_toolnumber) 
        self.widgets.raise_z_on_toolchange.set_active(self.data.raise_z_on_toolchange) 
        self.widgets.allow_spindle_on_toolchange.set_active(self.data.allow_spindle_on_toolchange)

    def on_GUI_config_next(self, *args):
        if self.widgets.GUIAXIS.get_active():
           self.data.frontend = 1
        elif self.widgets.GUITKEMC.get_active():
           self.data.frontend = 2
        else:
            self.data.frontend = 3
        self.data.default_linear_velocity = self.widgets.default_linear_velocity.get_value()/60
        self.data.max_linear_velocity = self.widgets.max_linear_velocity.get_value()/60
        self.data.min_linear_velocity = self.widgets.min_linear_velocity.get_value()/60
        self.data.default_angular_velocity = self.widgets.default_angular_velocity.get_value()/60
        self.data.max_angular_velocity = self.widgets.max_angular_velocity.get_value()/60
        self.data.min_angular_velocity = self.widgets.min_angular_velocity.get_value()/60
        self.data.editor = self.widgets.editor.get_text()
        if self.data.units == 0 :self.data.increments_imperial = self.widgets.increments.get_text()
        else:self.data.increments_metric = self.widgets.increments.get_text()
        self.data.geometry = self.widgets.geometry.get_text()
        self.data.position_offset = self.widgets.position_offset.get_active()
        self.data.position_feedback = self.widgets.position_feedback.get_active()
        self.data.require_homing = self.widgets.require_homing.get_active()
        self.data.individual_homing = self.widgets.individual_homing.get_active()
        self.data.restore_joint_position = self.widgets.restore_joint_position.get_active() 
        self.data.tooloffset_on_w = self.widgets.tooloffset_on_w.get_active() 
        self.data.restore_toolnumber = self.widgets.restore_toolnumber.get_active() 
        self.data.raise_z_on_toolchange = self.widgets.raise_z_on_toolchange.get_active() 
        self.data.allow_spindle_on_toolchange = self.widgets.allow_spindle_on_toolchange.get_active()
        if not self.data.mesa5i20:
           self.widgets.druid1.set_page(self.widgets.pp1pport)
           return True
        self.data.pyvcp = self.widgets.pyvcp.get_active()
        self.data.pyvcpconnect = self.widgets.pyvcpconnect.get_active() 
        if self.data.pyvcp == True:
           if self.widgets.pyvcpblank.get_active() == True:
              self.data.pyvcpname = "blank.xml"
              self.pyvcphaltype = 0
           if self.widgets.pyvcp1.get_active() == True:
              self.data.pyvcpname = "spindle.xml"
              self.data.pyvcphaltype = 1
           if self.widgets.pyvcp2.get_active() == True:
              self.data.pyvcpname = "xyzjog.xml"
              self.data.pyvcphaltype = 2
              self.data.halui = True 
              self.widgets.halui.set_active(True) 
              self.data.halui_cmd1="G0 G53 Z0"
              self.data.halui_cmd2="G28"
              self.data.halui_cmd3="G92 X0"
              self.data.halui_cmd4="G92 Y0"
              self.data.halui_cmd5="G92 Z0"
              self.data.halui_cmd6="G92.1"               
           if self.widgets.pyvcpexist.get_active() == True:
              self.data.pyvcpname = "custompanel.xml"
           else:
              if os.path.exists(os.path.expanduser("~/emc2/configs/%s/custompanel.xml" % self.data.machinename)):
                 if not self.warning_dialog(_("OK to replace existing custom pyvcp panel and custom_postgui.hal file ?\nExisting custompanel.xml and custom_postgui.hal will be renamed custompanel_backup.xml and postgui_backup.hal.\nAny existing file named custompanel_backup.xml and custom_postgui.hal will be lost. "),False):
                   return True

    def do_exclusive_inputs(self, pin):
        if self.in_pport_prepare: return
        exclusive = {
            HOME_X: (MAX_HOME_X, MIN_HOME_X, BOTH_HOME_X, ALL_HOME),
            HOME_Y: (MAX_HOME_Y, MIN_HOME_Y, BOTH_HOME_Y, ALL_HOME),
            HOME_Z: (MAX_HOME_Z, MIN_HOME_Z, BOTH_HOME_Z, ALL_HOME),
            HOME_A: (MAX_HOME_A, MIN_HOME_A, BOTH_HOME_A, ALL_HOME),

            MAX_HOME_X: (HOME_X, MIN_HOME_X, MAX_HOME_X, BOTH_HOME_X, ALL_LIMIT, ALL_HOME),
            MAX_HOME_Y: (HOME_Y, MIN_HOME_Y, MAX_HOME_Y, BOTH_HOME_Y, ALL_LIMIT, ALL_HOME),
            MAX_HOME_Z: (HOME_Z, MIN_HOME_Z, MAX_HOME_Z, BOTH_HOME_Z, ALL_LIMIT, ALL_HOME),
            MAX_HOME_A: (HOME_A, MIN_HOME_A, MAX_HOME_A, BOTH_HOME_A, ALL_LIMIT, ALL_HOME),

            MIN_HOME_X: (HOME_X, MAX_HOME_X, BOTH_HOME_X, ALL_LIMIT, ALL_HOME),
            MIN_HOME_Y: (HOME_Y, MAX_HOME_Y, BOTH_HOME_Y, ALL_LIMIT, ALL_HOME),
            MIN_HOME_Z: (HOME_Z, MAX_HOME_Z, BOTH_HOME_Z, ALL_LIMIT, ALL_HOME),
            MIN_HOME_A: (HOME_A, MAX_HOME_A, BOTH_HOME_A, ALL_LIMIT, ALL_HOME),

            BOTH_HOME_X: (HOME_X, MAX_HOME_X, MIN_HOME_X, ALL_LIMIT, ALL_HOME),
            BOTH_HOME_Y: (HOME_Y, MAX_HOME_Y, MIN_HOME_Y, ALL_LIMIT, ALL_HOME),
            BOTH_HOME_Z: (HOME_Z, MAX_HOME_Z, MIN_HOME_Z, ALL_LIMIT, ALL_HOME),
            BOTH_HOME_A: (HOME_A, MAX_HOME_A, MIN_HOME_A, ALL_LIMIT, ALL_HOME),

            MIN_X: (BOTH_X, BOTH_HOME_X, MIN_HOME_X, ALL_LIMIT),
            MIN_Y: (BOTH_Y, BOTH_HOME_Y, MIN_HOME_Y, ALL_LIMIT),
            MIN_Z: (BOTH_Z, BOTH_HOME_Z, MIN_HOME_Z, ALL_LIMIT),
            MIN_A: (BOTH_A, BOTH_HOME_A, MIN_HOME_A, ALL_LIMIT),

            MAX_X: (BOTH_X, BOTH_HOME_X, MIN_HOME_X, ALL_LIMIT),
            MAX_Y: (BOTH_Y, BOTH_HOME_Y, MIN_HOME_Y, ALL_LIMIT),
            MAX_Z: (BOTH_Z, BOTH_HOME_Z, MIN_HOME_Z, ALL_LIMIT),
            MAX_A: (BOTH_A, BOTH_HOME_A, MIN_HOME_A, ALL_LIMIT),

            BOTH_X: (MIN_X, MAX_X, MIN_HOME_X, MAX_HOME_X, BOTH_HOME_X, ALL_LIMIT),
            BOTH_Y: (MIN_Y, MAX_Y, MIN_HOME_Y, MAX_HOME_Y, BOTH_HOME_Y, ALL_LIMIT),
            BOTH_Z: (MIN_Z, MAX_Z, MIN_HOME_Z, MAX_HOME_Z, BOTH_HOME_Z, ALL_LIMIT),
            BOTH_A: (MIN_A, MAX_A, MIN_HOME_A, MAX_HOME_A, BOTH_HOME_A, ALL_LIMIT),

            ALL_LIMIT: (
                MIN_X, MAX_X, BOTH_X, MIN_HOME_X, MAX_HOME_X, BOTH_HOME_X,
                MIN_Y, MAX_Y, BOTH_Y, MIN_HOME_Y, MAX_HOME_Y, BOTH_HOME_Y,
                MIN_Z, MAX_Z, BOTH_Z, MIN_HOME_Z, MAX_HOME_Z, BOTH_HOME_Z,
                MIN_A, MAX_A, BOTH_A, MIN_HOME_A, MAX_HOME_A, BOTH_HOME_A),
            ALL_HOME: (
                HOME_X, MIN_HOME_X, MAX_HOME_X, BOTH_HOME_X,
                HOME_Y, MIN_HOME_Y, MAX_HOME_Y, BOTH_HOME_Y,
                HOME_Z, MIN_HOME_Z, MAX_HOME_Z, BOTH_HOME_Z,
                HOME_A, MIN_HOME_A, MAX_HOME_A, BOTH_HOME_A),
        } 

        p = 'pp1Ipin%d' % pin
        v = self.widgets[p].get_active()
        ex = exclusive.get(hal_input_names[v], ())

        for pin1 in (10,11,12,13,15):
            if pin1 == pin: continue
            p = 'pp1Ipin%d' % pin1
            v1 = hal_input_names[self.widgets[p].get_active()]
            if v1 in ex or v1 == v:
                self.widgets[p].set_active(hal_input_names.index(UNUSED_INPUT))

    def on_pin10_changed(self, *args):
        self.do_exclusive_inputs(10)
    def on_pin11_changed(self, *args):
        self.do_exclusive_inputs(11)
    def on_pin12_changed(self, *args):
        self.do_exclusive_inputs(12)
    def on_pin13_changed(self, *args):
        self.do_exclusive_inputs(13)
    def on_pin15_changed(self, *args):
        self.do_exclusive_inputs(15)

    def on_mesa_boardname_changed(self, *args):
        board = self.widgets.mesa_boardname.get_active_text()
        model = self.widgets.mesa_firmware.get_model()
        model.clear()
        for search, item in enumerate(mesafirmwaredata):
            d = mesafirmwaredata[search]
            if not d[0] == board:continue
            model.append((d[1],))
        
        self.widgets.mesa_firmware.set_active(0)  
        self.on_mesa_firmware_changed()

    def on_mesa_firmware_changed(self, *args):
        board = self.widgets.mesa_boardname.get_active_text()
        firmware = self.widgets.mesa_firmware.get_active_text()
        for search, item in enumerate(mesafirmwaredata):
            d = mesafirmwaredata[search]
            if not d[0] == board:continue
            if d[1] == firmware:
                self.widgets.numof_mesa_encodergens.set_range(0,d[2])
                self.widgets.numof_mesa_encodergens.set_value(d[2])
                self.widgets.numof_mesa_pwmgens.set_range(0,d[3])
                self.widgets.numof_mesa_pwmgens.set_value(d[3])
                self.widgets.numof_mesa_stepgens.set_range(0,d[4])
                self.widgets.numof_mesa_stepgens.set_value(d[4])
            self.on_gpio_update()

    def on_gpio_update(self, *args):
        board = self.widgets.mesa_boardname.get_active_text()
        firmware = self.widgets.mesa_firmware.get_active_text()
        for search, item in enumerate(mesafirmwaredata):
            d = mesafirmwaredata[search]
            if not d[0] == board:continue
            if d[1] == firmware:      
                i = (int(self.widgets.numof_mesa_pwmgens.get_value()) * 3)
                j = (int(self.widgets.numof_mesa_stepgens.get_value()) * d[6])
                k = (int(self.widgets.numof_mesa_encodergens.get_value()) * d[5])
                total = (d[8]-i-j-k)
                self.widgets.numof_mesa_gpio.set_text("%d" % total)


    def on_mesa5i20_prepare(self, *args):
        self.data.help = "help-mesa.txt"
        # If we just reloaded a config then update the page right now
        # as we already know what board /firmware /components are wanted.
        if not self.widgets.createconfig.get_active() and not self.intrnldata.mesa_configured  :
            self.set_mesa_options(self.data.mesa_boardname,self.data.mesa_firmware,self.data.numof_mesa_pwmgens,
                    self.data.numof_mesa_stepgens,self.data.numof_mesa_encodergens)
        elif not self.intrnldata.mesa_configured:
            self.widgets.con2tab.set_sensitive(0)
            self.widgets.con2table.set_sensitive(0)
            self.widgets.con3table.set_sensitive(0)
            self.widgets.con3tab.set_sensitive(0)
            self.widgets.con4tab.set_sensitive(0)
            self.widgets.con4table.set_sensitive(0)
            self.widgets.con5table.set_sensitive(0)
            self.widgets.con5tab.set_sensitive(0)
            
        
  
    # This method converts data from the GUI page to signal names for pncconf's mesa data variables
    # It starts by checking pin type to set up the proper lists to search
    # then depending on the pin type widget data is converted to signal names.
    # if the signal name is not in the list add it to Human_names, signal_names
    # and disc-saved signalname lists
    # if encoder, pwm, or stepper pins the related pin are also set properly
    # eg if pin 0 is [encoder-A} then pin 2 is set to [encoder -B] and
    # pin 4 to [encoder-C]   
    def on_mesa5i20_next(self,*args):
        if not self.intrnldata.mesa_configured:
            self.warning_dialog(_("You need to configure the mesa page.\n Choose the board type, firmware, component amounts and press 'Accept component changes' button'"),True)
            self.widgets.druid1.set_page(self.widgets.mesa5i20)
            return True
        for connector in self.data.mesa_currentfirmwaredata[11] :
            for pin in range(0,24):
                foundit = 0
                p = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin}
                pinv = 'm5i20c%(con)dpin%(num)dinv' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}
                pintype = self.widgets[ptype].get_active_text()
                selection = self.widgets[p].get_active_text()
                if pintype in (ENCB,ENCI,ENCM,PWMD,PWME,STEPB): continue
                # type GPIO input
                if pintype == GPIOI:
                    nametocheck = human_input_names
                    signaltocheck = hal_input_names
                    addsignalto = self.data.halinputsignames
                # type gpio output and open drain
                elif pintype in (GPIOO,GPIOD):
                    nametocheck = human_output_names
                    signaltocheck = hal_output_names
                    addsignalto = self.data.haloutputsignames
                #type encoder
                elif pintype == ENCA:
                    nametocheck = human_encoder_input_names
                    signaltocheck = hal_encoder_input_names
                    addsignalto = self.data.halencoderinputsignames
                # type PWM gen
                elif pintype in( PWMP,PDMP):
                    nametocheck = human_pwm_output_names
                    signaltocheck = hal_pwm_output_names
                    addsignalto = self.data.halpwmoutputsignames
                # type step gen
                elif pintype == STEPA:
                    nametocheck = human_stepper_names
                    signaltocheck = hal_stepper_names
                    addsignalto = self.data.halsteppersignames
                else :
                    print "error unknown pin type"
                    return
                # check apropriote signal array for current signalname
                # if not found, user made a new signalname -add it to array
                for index , i in enumerate(nametocheck):
                    if selection == i : 
                        foundit = True
                        #print "found it",nametocheck[index],"in ",p,"\n"
                        break         
                # **Start widget to data Convertion**                    
                # for encoder pins
                if pintype == ENCA :
                    if not foundit:
                        print " adding encoder pinname\n"
                        model = self.widgets[p].get_model()
                        model.append((selection+"-a",))
                        self.widgets[p].set_active( len(model))
                        index = index +1
                        for ending in ("-a","-b","-i","-m"):
                            signaltocheck.append ((selection + ending))
                            nametocheck.append ((selection + ending))
                            addsignalto.append ((selection + ending))
                    # set related encoder pins
                    flag = 1
                    if selection == "Unused Encoder":flag = 0
                    if pin in (1,13):
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin-1}
                        self.data[d] = signaltocheck[(index+1)*flag]
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+3}
                        self.data[d] = signaltocheck[(index+2)*flag]
                    elif pin in (3,15):
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin-1}
                        self.data[d] = signaltocheck[(index+1)*flag]
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+2}
                        self.data[d] = signaltocheck[(index+2)*flag]  
                    else:
                        print"Encoder pin config error"
                        continue
                    if self.data.mesa_currentfirmwaredata[5] == 4:                           
                            for count, name in enumerate((1,3,13,15)):
                                if name == pin:
                                    if connector == 3: count=count+4
                                    d = 'm5i20c%(con)dpin%(num)d' % {'con':4 ,'num': count}
                                    self.data[d] = signaltocheck[(index+3)*flag]
                # for PWM pins
                elif pintype in (PWMP,PDMP) :
                    if not foundit:
                        model = self.widgets[p].get_model()
                        model.append((selection+"-pulse",))
                        index = index +1
                        for ending in ("-pulse","-dir","-enable"):
                            signaltocheck.append ((selection + ending))
                            nametocheck.append ((selection + ending))
                            addsignalto.append ((selection + ending))
                    # set related pwm pins
                    flag = 1
                    if selection == "Unused PWM Gen":flag = 0
                    if pin in (6,7,18,19):
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+2}
                        self.data[d] = signaltocheck[(index+1)*flag]
                        d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+4}
                        self.data[d] = signaltocheck[(index+2)*flag]
                    else:
                        print "PWM pin config error"
                        continue
                    # for stepgen pins
                elif pintype == STEPA :
                    if not foundit:
                        model = self.widgets[p].get_model()
                        model.append((selection+"-step",))
                        index = index +1
                        for ending in ("-step","-dir"):
                            signaltocheck.append ((selection + ending))
                            nametocheck.append ((selection + ending))
                            addsignalto.append ((selection + ending))
                    # set related stepgen pins
                    flag = 1
                    if selection == "Unused StepGen":flag = 0
                    d = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+1}
                    self.data[d] = signaltocheck[(index+1)*flag]
                    
                # for input and output
                elif pintype in(GPIOI,GPIOO,GPIOD):
                    if not foundit:
                        model = self.widgets[p].get_model()
                        index = index +1
                        model.append((selection,))
                        signaltocheck.append ((selection))
                        nametocheck.append ((selection))
                        addsignalto.append ((selection))
                else:
                        print "pintype error pintype =",pintype
                #  set data from widget for current pin
                self.data[p] = signaltocheck[index]
                self.data[pinv] = self.widgets[pinv].get_active()
        self.data.mesa_pwm_frequency = self.widgets.mesa_pwm_frequency.get_value()
        self.data.mesa_pdm_frequency = self.widgets.mesa_pdm_frequency.get_value()
        self.data.mesa_watchdog_timeout = self.widgets.mesa_watchdog_timeout.get_value()
        if self.data.number_pports<1:
           self.widgets.druid1.set_page(self.widgets.xaxismotor)
           return True

    def on_m5i20panel_clicked(self, *args):self.m5i20test(self)
    
    def on_mesa_pintype_changed(self, widget,connector,pin):
         
               # if self.in_mesa_prepare == True: return
               #print "got to pintype change method ",connector,pin,"\n"
         
                p = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}    
                old = self.data[ptype]
                new = self.widgets[ptype].get_active_text()    
                if (new == None or new == old): return 
                if old == GPIOI and new in (GPIOO,GPIOD):
                    print "switch GPIO input ",p," to output",new
                    model = self.widgets[p].get_model()
                    blocksignal = "mesasignalhandlerc%ipin%i"% (connector,pin)  
                    self.widgets[p].handler_block(self.intrnldata[blocksignal])
                    model.clear()
                    for name in human_output_names: model.append((name,))
                    self.widgets[p].handler_unblock(self.intrnldata[blocksignal])  
                    self.widgets[p].set_active(0)
                    self.data[p] = UNUSED_OUTPUT
                    self.data[ptype] = new
                elif old in (GPIOO,GPIOD) and new == GPIOI:
                    print "switch GPIO output ",p,"to input"
                    model = self.widgets[p].get_model()
                    model.clear()
                    blocksignal = "mesasignalhandlerc%ipin%i"% (connector,pin)  
                    self.widgets[p].handler_block(self.intrnldata[blocksignal])              
                    for name in human_input_names:
                        if self.data.limitshared or self.data.limitsnone:
                            if name in human_names_limit_only: continue 
                        if self.data.limitswitch or self.data.limitsnone:
                            if name in human_names_shared_home: continue                          
                        if self.data.homenone or self.data.limitshared:
                            if name in (_("X Home"), _("Y Home"), _("Z Home"), _("A Home"), _("All Home")): continue
                        model.append((name,))
                    self.widgets[p].handler_unblock(self.intrnldata[blocksignal])  
                    self.widgets[p].set_active(0)
                    self.data[p] = UNUSED_INPUT
                    self.data[ptype] = new
                elif (old == GPIOI and new == GPIOD) :
                    print "switch GPIO output ",p,"to open drain"
                    self.data[ptype] = new
                elif (old == GPIOD and new == GPIOO):
                    print "switch GPIO opendrain ",p,"to output"
                    self.data[ptype] = new
                elif old == PWMP and new == PDMP:
                    print "switch PWM  ",p,"to PDM"
                    self.data[ptype] = new
                elif old == PDMP and new == PWMP:
                    print "switch PDM  ",p,"to PWM"
                    self.data[ptype] = new
                else: print "pintype error in pinchanged method old,new ",old,new,"\n"

    def on_mesa_component_value_changed(self, *args):
        self.in_mesa_prepare = True
        self.data.mesa_pwm_frequency = self.widgets.mesa_pwm_frequency.get_value()
        self.data.mesa_pdm_frequency = self.widgets.mesa_pdm_frequency.get_value()
        self.data.mesa_watchdog_timeout = self.widgets.mesa_watchdog_timeout.get_value()
        numofpwmgens = self.data.numof_mesa_pwmgens = int(self.widgets.numof_mesa_pwmgens.get_value())
        numofstepgens = self.data.numof_mesa_stepgens = int(self.widgets.numof_mesa_stepgens.get_value())
        numofencoders = self.data.numof_mesa_encodergens = int(self.widgets.numof_mesa_encodergens.get_value())
        board = self.data.mesa_boardname = self.widgets.mesa_boardname.get_active_text()
        firmware = self.data.mesa_firmware = self.widgets.mesa_firmware.get_active_text()
        self.set_mesa_options(board,firmware,numofpwmgens,numofstepgens,numofencoders)


    # This method sets up the mesa GUI page.
    # it changes the component comboboxes according to the firmware max and user requested amounts
    # it adds signal names to the signal name combo boxes according to component type and in the
    # case of GPIO options selected on the basic page such as limit/homing types.
    # it will grey out I/O tabs according to the selected board type. 
    # it uses GTK signal blocking to block on_mesa_pin_change and on_mesa_pintype_changed methods.
    # Since this method is for intialization, there is no need to check for changes and this speeds up
    # the update.  
    # 'mesafirmwaredata' holds all the firmware data.
    # 'self.data.mesa_currentfirmwaredata' hold the current selected firmware data
    def set_mesa_options(self,board,firmware,numofpwmgens,numofstepgens,numofencoders):
        for search, item in enumerate(mesafirmwaredata):
            d = mesafirmwaredata[search]
            if not d[0] == board:continue
            if d[1] == firmware:
                self.data.mesa_currentfirmwaredata = mesafirmwaredata[search]
                break
        self.widgets.con3table.set_sensitive(1) 
        self.widgets.con3tab.set_sensitive(1)
        self.widgets.con4table.set_sensitive(1) 
        self.widgets.con4tab.set_sensitive(1)
        if self.data.mesa_currentfirmwaredata[0] == "5i22":
            self.widgets.con5tab.set_sensitive(1)
            self.widgets.con5table.set_sensitive(1)
        else:
            self.widgets.con5tab.set_sensitive(0)
            self.widgets.con5table.set_sensitive(0)
        if self.data.mesa_currentfirmwaredata[0] == "7i43":
            self.widgets.con2table.set_sensitive(0)
            self.widgets.con2tab.set_sensitive(0)
        else:
            self.widgets.con2table.set_sensitive(1) 
            self.widgets.con2tab.set_sensitive(1)
        for concount,connector in enumerate(self.data.mesa_currentfirmwaredata[11]) :
            for pin in range (0,24):
                firmptype,compnum = self.data.mesa_currentfirmwaredata[12+pin+(concount*24)]
#                if connector == 2:
#                    print firmptype,"firmtype\n",compnum,"pinnum ",pin,",concount ",concount,"\n"               
                p = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}
                pinv = 'm5i20c%(con)dpin%(num)dinv' % {'con':connector ,'num': pin}
                blocksignal = "mesasignalhandlerc%ipin%i" % (connector,pin)    
                ptypeblocksignal  = "mesaptypesignalhandlerc%ipin%i" % (connector,pin)               
                # convert widget[ptype] to component specified in firmwaredata   
                   
                # ---SETUP GUI FOR ENCODER FAMILY COMPONENT--- 
                # check that we are not converting more encoders that user requested
                # if we are we will change the variable 'firmtype' to ask for GPIO
                if firmptype in ( ENCA,ENCB,ENCI,ENCM ): 
                    if numofencoders >= (compnum+1):
                        # if the combobox is not already displaying the right component:
                        # then we need to set up the comboboxes for this pin, otherwise skip it
                        if not self.widgets[ptype].get_active_text() in ( ENCA,ENCB,ENCI,ENCM ):  
                            self.widgets[pinv].set_sensitive(0)
                            self.widgets[pinv].set_active(0)                      
                            self.widgets[ptype].handler_block(self.intrnldata[ptypeblocksignal])
                            model = self.widgets[ptype].get_model()
                            model.clear() 
                            model.append((firmptype,))
                            self.widgets[ptype].handler_unblock(self.intrnldata[ptypeblocksignal])
                            self.widgets[p].handler_block(self.intrnldata[blocksignal]) 
                            self.widgets[ptype].set_active(0)
                            model = self.widgets[p].get_model()
                            model.clear()
                            # we only add every 4th human name so the user can only select
                            # the encoder's 'A' signal name. If its the other signals
                            # we can add them all because pncconf controls what the user sees
                            if firmptype == ENCA: 
                                temp = -1                               
                                for name in human_encoder_input_names:                      
                                    temp = temp +1
                                    if temp in (2,3): continue
                                    if temp == 4:
                                        temp = 0
                                        continue
                                    model.append((name,))
                                self.widgets[p].handler_unblock(self.intrnldata[blocksignal])
                                self.widgets[p].set_active(0)
                                self.widgets[p].set_sensitive(1)
                                self.widgets[ptype].set_sensitive(1)
                            elif firmptype in(ENCB,ENCI,ENCM):                           
                                for name in human_encoder_input_names:model.append((name,)) 
                                self.widgets[p].handler_unblock(self.intrnldata[blocksignal])  
                                self.widgets[p].set_sensitive(0)
                                self.widgets[ptype].set_sensitive(0)
                                self.widgets[p].set_active(0)  
                            # if the data stored ptype is the encoder family then use the data stored signal name
                            # else set to unused_encoder signal name 
                            if self.data[ptype] in (ENCA,ENCB,ENCI,ENCM): 
                                #print self.data[p]
                                self.widgets[p].set_active(0) 
                                model = self.widgets[p].get_model()
                                for search,item in enumerate(model):
                                    if model[search][0]  == human_encoder_input_names[hal_encoder_input_names.index(self.data[p])]:
                                        self.widgets[p].set_active(search)
                                        break                                          
                            else:
                                self.data[p] =  UNUSED_ENCODER
                                self.data[ptype] = firmptype
                                self.widgets[p].set_active(0)  
                            continue                
                    else:   
                        # user requested this encoder component to be GPIO instead
                        # We cheat a little and tell the rest of the method that the firmware says
                        # it should be GPIO
                        firmptype = GPIOI
                # ---SETUP GUI FOR PWM FAMILY COMPONENT---
                elif firmptype in ( PWMP,PWMD,PWME,PDMP,PDMD,PDME ):
                    if numofpwmgens >= (compnum+1):
                        if not self.widgets[ptype].get_active_text() in ( PWMP,PWMD,PWME,PDMP,PDMD,PDME ):
                            self.widgets[pinv].set_sensitive(0)
                            self.widgets[pinv].set_active(0)
                            self.widgets[ptype].handler_block(self.intrnldata[ptypeblocksignal])
                            model = self.widgets[ptype].get_model()
                            model.clear() 
                            model.append((firmptype,))
                            temp = pintype_names[12]
                            model.append((temp,))
                            self.widgets[ptype].handler_unblock(self.intrnldata[ptypeblocksignal])
                            self.widgets[p].handler_block(self.intrnldata[blocksignal])
                            model = self.widgets[p].get_model()
                            model.clear()
                            if firmptype in(PWMP,PDMP):
                                temp = -1                               
                                for name in human_pwm_output_names:                       
                                    temp = temp +1
                                    if temp == 2: continue
                                    if temp == 3:
                                        temp = 0
                                        continue
                                    model.append((name,))
                                self.widgets[ptype].set_sensitive(1)
                                self.widgets[p].set_sensitive(1)
                                self.widgets[p].set_active(0)
                                self.widgets[p].handler_unblock(self.intrnldata[blocksignal])
                            elif firmptype in (PWMD,PWME,PDMD,PDME):                             
                                self.widgets[p].set_sensitive(0)
                                for name in human_pwm_output_names: model.append((name,))
                                self.widgets[p].handler_unblock(self.intrnldata[blocksignal])
                                self.widgets[p].set_active(0) 
                                self.widgets[ptype].set_sensitive(0)
                # This is for GPIO to PWM conversion
                # check to see data is already set to PWM family
                # if in PWM family - set to data signal name
                # if in GPIO family - changed to unused_PWM signal name 
                            if self.data[ptype] in (PWMP,PWMD,PWME,PDMP,PDMD,PDME): 
                                if self.data[ptype] in (PWMP,PWMD,PWME):self.widgets[ptype].set_active(0)
                                else:self.widgets[ptype].set_active(1)
                                self.widgets[p].set_active(0)
                                model = self.widgets[p].get_model()
                                for search,item in enumerate(model):
                                    if model[search][0]  == human_pwm_output_names[hal_pwm_output_names.index(self.data[p])]:
                                        self.widgets[p].set_active(search)
                                        break    
                            else:
                                self.data[p] =  UNUSED_PWM
                                self.data[ptype] = firmptype
                                self.widgets[p].set_active(0) 
                                if firmptype in (PWMP,PWMD,PWME):self.widgets[ptype].set_active(0)
                                else:self.widgets[ptype].set_active(1) 
                            continue
                    else:
                        firmptype = GPIOI
                # ---SETUP FOR STEPPER FAMILY COMPONENT---
                elif firmptype in (STEPA,STEPB):  
                    if numofstepgens >= (compnum+1):               
                        if not self.widgets[ptype].get_active_text() in (STEPA,STEPB):
                            self.widgets[pinv].set_sensitive(0)
                            self.widgets[pinv].set_active(0)
                            self.widgets[ptype].handler_block(self.intrnldata[ptypeblocksignal])
                            model = self.widgets[ptype].get_model()
                            model.clear() 
                            model.append((firmptype,))
                            self.widgets[ptype].handler_unblock(self.intrnldata[ptypeblocksignal])                  
                            self.widgets[p].handler_block(self.intrnldata[blocksignal])
                            model = self.widgets[p].get_model()
                            model.clear() 
                            # We have to step over some extra signalnames that hostmot2 currently
                            # doesn't support yet. support missing for direct coil control stepping
                            if firmptype == STEPA:
                                temp = -1                              
                                for name in (human_stepper_names):
                                    temp = temp + 1
                                    if temp in(2,3,4,5): continue
                                    if temp == 6:
                                        temp = 0
                                        continue
                                    model.append((name,))
                                self.widgets[p].set_sensitive(1)
                                self.widgets[ptype].set_sensitive(1)
                                self.widgets[p].handler_unblock(self.intrnldata[blocksignal])
                            elif firmptype == STEPB:                               
                                    for name in human_stepper_names: model.append((name,))
                                    self.widgets[p].handler_unblock(self.intrnldata[blocksignal])
                                    self.widgets[p].set_sensitive(0)
                                    self.widgets[p].set_active(0)
                                    self.widgets[ptype].set_sensitive(0) 
                            self.widgets[p].set_wrap_width(1)
                            if self.data[ptype] in (STEPA,STEPB): 
                                self.widgets[ptype].set_active(0)  
                                self.widgets[p].set_active(0)
                                model = self.widgets[p].get_model()
                                for search,item in enumerate(model):
                                    if model[search][0]  == human_stepper_names[hal_stepper_names.index(self.data[p])]:
                                        self.widgets[p].set_active(search)
                                        break
                            else:
                                self.data[p] =  UNUSED_STEPGEN
                                self.data[pinv] = 0
                                self.data[ptype] = firmptype
                                self.widgets[p].set_active(0)
                                self.widgets[ptype].set_active(0)                     
                            continue
                    else:firmptype = GPIOI
                # ---SETUP FOR GPIO FAMILY COMPONENT---
                # first check to see if firmware says it should be in GPIO family
                # (note this can be because firmware says it should be some other 
                # type but the user wants to deselect it so as to use it as GPIO
                # this is done in the firmtype checks before this check. 
                # They will change firmtype variable to GPIOI)       
                # check if firmtype is in GPIO family
                # check if widget is already configured
                # check to see if data says it is in GPIO family
                # if not change datatype to GPIOI and signal to unused input
                # block GTK signals from widget pintype and add names to ptype combobox
                # block GTK signals from widget pin 
                # if GPIOI then add input signal names to pin combobox exclude unselected signal names
                # if not then add output signal names 
                if firmptype in (GPIOI,GPIOO,GPIOD): 
                    if not self.widgets[ptype].get_active_text() in (GPIOI,GPIOO,GPIOD):                 
                        if not self.data[ptype] in (GPIOI,GPIOO,GPIOD): 
                            self.data[p] =  UNUSED_INPUT
                            self.data[pinv] = 0
                            self.data[ptype] = GPIOI
                        self.widgets[p].set_sensitive(1)
                        self.widgets[pinv].set_sensitive(1)
                        self.widgets[ptype].set_sensitive(1)
                        self.widgets[ptype].handler_block(self.intrnldata[ptypeblocksignal])
                        model = self.widgets[ptype].get_model()
                        model.clear()
                        #  add 'input, output, and open drain' names to GPIO combobox
                        for j in (0,1,2):
                            temp = pintype_names[j]
                            model.append((temp,))
                        self.widgets[ptype].handler_unblock(self.intrnldata[ptypeblocksignal])
                        self.widgets[p].handler_block(self.intrnldata[blocksignal]) 
                        model = self.widgets[p].get_model()
                        model.clear()
                        # signal names for GPIO INPUT
                        # add human names to widget excluding signalnames specified in homing limit and spindle
                        if self.data[ptype] == GPIOI:  
                            self.widgets[ptype].set_active(0)                                     
                            for name in human_input_names:
                                if self.data.limitshared or self.data.limitsnone:
                                    if name in human_names_limit_only: continue 
                                if self.data.limitswitch or self.data.limitsnone:
                                    if name in human_names_shared_home: continue                          
                                if self.data.homenone or self.data.limitshared:
                                    if name in (_("X Home"), _("Y Home"), _("Z Home"), _("A Home"),_("All home")): continue
                                model.append((name,))  
                            self.widgets[p].handler_unblock(self.intrnldata[blocksignal])  
                            #self.widgets[p].set_active(0)
                            model = self.widgets[p].get_model()
                            for search,item in enumerate(model):
                                if model[search][0]  == human_input_names[hal_input_names.index(self.data[p])]:
                                    self.widgets[p].set_active(search)
                                    break
                            self.widgets[p].set_wrap_width(3)
                            self.widgets[pinv].set_active(self.data[pinv])
                            continue
                        # signal names for GPIO OUTPUT and OPEN DRAIN OUTPUT
                        elif self.data[ptype] in (GPIOO,GPIOD):     
                            if firmptype == GPIOO:self.widgets[ptype].set_active(2)
                            else:self.widgets[ptype].set_active(1)  
                            for name in human_output_names: model.append((name,))
                            self.widgets[p].handler_unblock(self.intrnldata[blocksignal])  
                            self.widgets[p].set_active(0)  
                            model = self.widgets[p].get_model()
                            for search,item in enumerate(model):
                                if model[search][0]  == human_output_names[hal_output_names.index(self.data[p])]:
                                    self.widgets[p].set_active(search)
                                    break   
                            self.widgets[p].set_wrap_width(3)
                            self.widgets[pinv].set_active(self.data[pinv])
                            continue  
   
        self.data.numof_mesa_stepgens = numofstepgens
        self.data.numof_mesa_pwmgens = numofpwmgens
        self.data.numof_mesa_encodergens = numofencoders
        temp = (numofstepgens * self.data.mesa_currentfirmwaredata[6])
        temp1 = (numofencoders * self.data.mesa_currentfirmwaredata[5])
        temp2 = (numofpwmgens * 3)
        total = (self.data.mesa_currentfirmwaredata[8]-temp-temp1-temp2)
        self.data.numof_mesa_gpio = total     
        self.widgets.numof_mesa_stepgens.set_value(numofstepgens)
        self.widgets.numof_mesa_encodergens.set_value(numofencoders)      
        self.widgets.numof_mesa_pwmgens.set_value(numofpwmgens)
        self.in_mesa_prepare = False   
        self.intrnldata.mesa_configured = True
       

    def on_mesa_pin_changed(self, widget, connector, pin):
                #if self.in_mesa_prepare == True: return       
                p = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}
                pinchanged =  self.widgets[p].get_active_text() 
                dataptype = self.data[ptype]
                used = 0
                #print"pin change method ",ptype," = ",dataptype,"active ",pinchanged,"\n"
                if dataptype in (ENCB,ENCI,ENCM,STEPB,PWMD,PWME,GPIOI,GPIOO,GPIOD):return
                # for stepgen pins
                if dataptype == STEPA:
                    #print"ptype step\n"
                    for index, name in enumerate(human_stepper_names):
                        if name == pinchanged:
                            if not pinchanged == "Unused StepGen":used = 1
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+1}
                            self.widgets[tochange].set_active((index+1)*used) 
                    return 
                # for encoder pins
                elif dataptype == ENCA: 
                    #print"ptype encoder\n"
                    nametocheck = human_encoder_input_names
                    signaltocheck = hal_encoder_input_names
                    addsignalto = self.data.halencoderinputsignames
                    unusedcheck = "Unused Encoder"
                # for PWM pins
                elif dataptype == PWMP: 
                    #print"ptype pwmp\n"
                    nametocheck = human_pwm_output_names
                    signaltocheck = hal_pwm_output_names
                    addsignalto = self.data.halpwmoutputsignames
                    unusedcheck = "Unused PWM Gen"
                else: 
                    print" pintype not found\n"
                    return   
                foundit = False            
                for index, name in enumerate(nametocheck):
                    if name == pinchanged:
                        if not pinchanged == unusedcheck:used = 1
                        # for encoder 0 amd 2 pins
                        if pin in (1,13):
                           # print"changing encoder b"
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin-1}
                            self.widgets[tochange].set_active((index+1)*used) 
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+3}
                            self.widgets[tochange].set_active((index+2)*used)
                        # for encoder 1 and 3 pins
                        elif pin in (3,15):
                            #print"changing encoder i"
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin-1}
                            self.widgets[tochange].set_active((index+1)*used) 
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+2}
                            self.widgets[tochange].set_active((index+2)*used) 
                        # for encoder mask pins
                        if self.data.mesa_currentfirmwaredata[5] == 4:                           
                            for count, name in enumerate((1,3,13,15)):
                                if name == pin:
                                    if connector == 3: count=count+4
                                    tochange = 'm5i20c%(con)dpin%(num)d' % {'con':4 ,'num': count}
                                    self.widgets[tochange].set_active((index+3)*used) 
                        # for pwm pins d and e
                        if pin in (6,7,18,19):
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+2}
                            self.widgets[tochange].set_active((index+1)*used)
                            tochange = 'm5i20c%(con)dpin%(num)d' % {'con':connector ,'num': pin+4}
                            self.widgets[tochange].set_active((index+2)*used)

    def on_pp1pport_prepare(self, *args):
        self.data.help = 5
        self.in_pport_prepare = True
        self.prepare_parport("pp1")
        c = self.data.pp1_direction
        if c:
                self.widgets.pp1pport.set_title(_("First Parallel Port set for OUTPUT"))
        else:
                self.widgets.pp1pport.set_title(_("First Parallel Port set for INPUT"))   

    def on_pp1pport_next(self, *args):
        self.next_parport("pp1")
        #self.findsignal("all-home")          
        #on_pport_back = on_pport_next
        if self.data.number_pports<2:
                self.widgets.druid1.set_page(self.widgets.xaxismotor)
                return True

    def on_pp1pport_back(self, *args):
         if not self.data.mesa5i20 :
                self.widgets.druid1.set_page(self.widgets.GUIconfig)
                return True

    def on_pp2pport_prepare(self, *args):
         self.data.help = 5
         self.prepare_parport("pp2")
         c = self.data.pp2_direction
         if c:
                self.widgets.pp2pport.set_title(_("Second Parallel Port set for OUTPUT"))
         else:
                self.widgets.pp2pport.set_title(_("Second Parallel Port set for INPUT"))

    def on_pp2pport_next(self, *args):
        self.next_parport("pp2")
        if self.data.number_pports<3:
                self.widgets.druid1.set_page(self.widgets.xaxismotor)
                return True

    def on_pp3pport_prepare(self, *args):
         self.prepare_parport("pp3")
         c = self.data.pp3_direction
         if c:
                self.widgets.pp3pport.set_title(_("Third Parallel Port set for OUTPUT"))
         else:
                self.widgets.pp3pport.set_title(_("Third Parallel Port set for INPUT"))
  
    def on_pp3pport_next(self, *args):
        self.data.help = 5
        self.next_parport("pp3")

    def prepare_parport(self,portname):
        for pin in (1,2,3,4,5,6,7,8,9,14,16,17):
            p = '%sOpin%d' % (portname,pin)
            model = self.widgets[p].get_model()
            model.clear()
            for name in human_output_names: model.append((name,))
            self.widgets[p].set_active(hal_output_names.index(self.data[p]))
            self.widgets[p].set_wrap_width(3)
            p = '%sOpin%dinv' % (portname, pin)
            self.widgets[p].set_active(self.data[p])
        for pin in (2,3,4,5,6,7,8,9,10,11,12,13,15):
            p = '%sIpin%d' % (portname, pin)
            model = self.widgets[p].get_model()
            model.clear()
            for name in human_input_names:
                    if self.data.limitshared or self.data.limitsnone:
                        if name in human_names_limit_only: continue 
                    if self.data.limitswitch or self.data.limitsnone:
                        if name in human_names_shared_home: continue                          
                    if self.data.homenone or self.data.limitshared:
                        if name in (_("Home X"), _("Home Y"), _("Home Z"), _("Home A"),_("All home")): continue         
                    model.append((name,))
            for search,item in enumerate(model):
                if model[search][0]  == human_input_names[hal_input_names.index(self.data[p])]:
                    self.widgets[p].set_active(search)
            self.widgets[p].set_wrap_width(3)
            p = '%sIpin%dinv' % (portname, pin)
            self.widgets[p].set_active(self.data[p])
        self.in_pport_prepare = False
        c = self.data[portname+"_direction"]
        for pin in (2,3,4,5,6,7,8,9):
            p = '%sOpin%dlabel' % (portname, pin)
            self.widgets[p].set_sensitive(c)
            p = '%sOpin%dinv' % (portname, pin)
            self.widgets[p].set_sensitive(c)
            p = '%sOpin%d' % (portname, pin)
            self.widgets[p].set_sensitive(c)
            if not c :self.widgets[p].set_active(hal_output_names.index("unused-output"))
            p = '%sIpin%dlabel' % (portname, pin)
            self.widgets[p].set_sensitive(not c)
            p = '%sIpin%d' % (portname, pin)
            self.widgets[p].set_sensitive(not c)
            if c :self.widgets[p].set_active(hal_input_names.index("unused-input"))
            p = '%sIpin%dinv' % (portname, pin)
            self.widgets[p].set_sensitive(not c)

    def next_parport(self,portname):
        #check input pins
        for pin in (2,3,4,5,6,7,8,9,10,11,12,13,15):           
            p = '%sIpin%d' % (portname, pin)       
            foundit = 0
            selection = self.widgets[p].get_active_text()
            for index , i in enumerate(human_input_names):
                if selection == i : 
                    foundit = True
                    break               
            if not foundit:
                model = self.widgets[p].get_model()
                model.append((selection,))
                g = human_input_names
                g.append ((selection))
                hal_input_names.append ((selection))
                self.data.halinputsignames.append ((selection))
            self.data[p] = hal_input_names[index]
            p = '%sIpin%dinv' % (portname, pin)
            self.data[p] = self.widgets[p].get_active()
        # check output pins
        for pin in (1,2,3,4,5,6,7,8,9,14,16,17):           
            foundit = 0
            p = '%sOpin%d' % (portname, pin)
            selection = self.widgets[p].get_active_text()
            for i in human_output_names:
               if selection == i : foundit = 1
            if not foundit:
                model = self.widgets[p].get_model()
                model.append((selection,))
                g = human_output_names
                g.append ((selection))
                hal_output_names.append ((selection))
                self.data.haloutputsignames.append ((selection))
            self.data[p] = hal_output_names[self.widgets[p].get_active()]
            p = '%sOpin%dinv' % (portname, pin)
            self.data[p] = self.widgets[p].get_active() 
    
    def on_parportpanel_clicked(self, *args):self.parporttest(self)
        
    def signal_sanity_check(self, *args):
        warnings = []
        do_warning = False
        for i in self.data.available_axes:
            if i == 's': continue
            step = self.data.findsignal(i+"-stepgen-step")
            enc = self.data.findsignal(i+"-encoder-a")
            pwm = self.data.findsignal(i+"-pwm-pulse")

            if step == "false" and pwm == "false" and enc =="false":  
                warnings.append(_("You forgot to designate a stepper or pwm signal for axis %s\n")% i)
                do_warning = True
            if not pwm == "false" and enc == "false": 
                warnings.append(_("You forgot to designate a servo encoder signal for axis %s\n")% i)
                do_warning = True
            if pwm == "false" and not enc == "false": 
                warnings.append(_("You forgot to designate a servo pwm signal for axis %s\n")% i)
                do_warning = True
            if not step == "false" and not enc == "false": 
                warnings.append(_("You can not have encoders with steppers for axis %s\n")% i)
                do_warning = True
            if not step == "false" and not pwm == "false": 
                warnings.append(_("You can not have both steppers and pwm signals for axis %s\n")% i)
                do_warning = True
        if do_warning: self.warning_dialog("\n".join(warnings),True)

    def on_xaxismotor_prepare(self, *args):
        self.data.help = "help-axismotor.txt"
        self.signal_sanity_check()
        self.axis_prepare('x')
    def on_xaxismotor_next(self, *args):  
        self.data.help = "help-axisconfig.txt"   
        self.axis_done('x')
        self.widgets.druid1.set_page(self.widgets.xaxis)
        return True
    def on_xaxismotor_back(self, *args):
        self.axis_done('x')  
        if self.data.number_pports==1:
                self.widgets.druid1.set_page(self.widgets.pp1pport)
                return True
        elif self.data.number_pports==2:
                self.widgets.druid1.set_page(self.widgets.pp2pport)
                return True
        elif self.data.number_pports==3:
                self.widgets.druid1.set_page(self.widgets.pp3pport)
                return True
        elif self.data.mesa5i20 :
                self.widgets.druid1.set_page(self.widgets.mesa5i20)
                return True    
 
    def on_yaxismotor_prepare(self, *args):
        self.data.help = "help-axismotor.txt"
        self.axis_prepare('y')
    def on_yaxismotor_next(self, *args):
        self.data.help = "help-axisconfig.txt"
        self.axis_done('y')
        self.widgets.druid1.set_page(self.widgets.yaxis)
        return True
    def on_yaxismotor_back(self, *args):      
        self.axis_done('y')  
        self.widgets.druid1.set_page(self.widgets.xaxis)
        return True
    
    def on_zaxismotor_prepare(self, *args):
        self.data.help = "help-axismotor.txt"
        self.axis_prepare('z')
    def on_zaxismotor_next(self, *args):
        self.data.help = "help-axisconfig.txt"
        self.axis_done('z')
        self.widgets.druid1.set_page(self.widgets.zaxis)
        return True
    def on_zaxismotor_back(self, *args):   
        self.axis_done('z')  
        if self.data.axes == 2:
            self.widgets.druid1.set_page(self.widgets.xaxis)
            return True    
        else:
            self.widgets.druid1.set_page(self.widgets.yaxis)
            return True

    def on_aaxismotor_prepare(self, *args):
        self.data.help = "help-axismotor.txt"
        self.axis_prepare('a')
    def on_aaxismotor_next(self, *args):
        self.data.help = "help-axisconfig.txt"
        self.axis_done('a')
        self.widgets.druid1.set_page(self.widgets.aaxis)
        return True
    def on_aaxismotor_back(self, *args):   
        self.axis_done('a')      
        self.widgets.druid1.set_page(self.widgets.zaxis)
        return True

    def on_xcalculatescale_clicked(self, *args): self.calculate_scale('x')
    def on_ycalculatescale_clicked(self, *args): self.calculate_scale('y')
    def on_zcalculatescale_clicked(self, *args): self.calculate_scale('z')
    def on_acalculatescale_clicked(self, *args): self.calculate_scale('a')
    def on_scalculatescale_clicked(self, *args): self.calculate_scale('s')

    def calculate_scale(self, axis):
        print axis
        w = self.widgets
        stepdriven = rotaryaxis = encoder = 1
        def get(n): return float(w[n].get_text())
        test = self.data.findsignal(axis+"-stepgen-step")    
        if test == "false":stepdriven = 0
        test = self.data.findsignal(axis+"-encoder-a")    
        if test == "false":encoder = 0
        w["steprev"].set_sensitive( stepdriven ) 
        w["microstep"].set_sensitive( stepdriven )
        w["encoderline"].set_sensitive( encoder )
        if not axis == 'a': rotaryaxis = 0
        w["wormden"].set_sensitive( rotaryaxis ) 
        w["wormnum"].set_sensitive( rotaryaxis )
        w["leadscrew"].set_sensitive( not rotaryaxis )
        self.widgets.scaledialog.set_title(_("Axis Scale Calculation"))
        self.widgets.scaledialog.show_all()
        result = self.widgets.scaledialog.run()
        #self.widgets['window1'].set_sensitive(0)
        self.widgets.scaledialog.hide()
        try:
            #w[axis + "encodercounts"].set_text( "%d" % ( 4 * float(w[axis+"encoderlines"].get_text())))   
            pitch = get("leadscrew")
            #if self.data.units == 1 or axis =='a' : pitch = 1./pitch
            if axis == 'a': factor =  ((get("wormnum") / get("wormden")))
            elif self.data.units == 1: factor = 1./pitch
            else: factor = pitch
            if stepdriven :
                scale = (factor * get("steprev") * get("microstep") * ((get("pulleynum") / get("pulleyden")))) 
            else:
                scale =  ( factor * float(w[("encoderline")].get_text()) * 4 * (get("pulleynum") / get("pulleyden")))
            if axis == 'a': scale = scale / 360
            w[axis + "calscale"].set_text("%.1f" % scale)
            w[axis + "scale"].set_text( "%.1f" % scale)
        except (ValueError, ZeroDivisionError):
            w[axis + "scale"].set_text( "")
        self.update_pps(axis)

    def axis_prepare(self, axis):
        test = self.data.findsignal(axis+"-stepgen-step")
        stepdriven = 1
        if test == "false":stepdriven = 0
        d = self.data
        w = self.widgets
        def set_text(n): w[axis + n].set_text("%s" % d[axis + n])
        def set_value(n): w[axis + n].set_value(d[axis + n])
        def set_active(n): w[axis + n].set_active(d[axis + n])
        model = w[axis+"drivertype"].get_model()
        model.clear()
        for i in drivertypes:
            model.append((i[1],))
        model.append((_("Custom"),))
        
        w["steprev"].set_text("%s" % d[axis+"steprev"])
        w["microstep"].set_text("%s" % d[axis +"microstep"])
        set_value("P")
        set_value("I")
        set_value("D")
        set_value("FF0")
        set_value("FF1")
        set_value("FF2")
        set_text("bias")
        set_text("deadband")
        set_text("steptime")
        set_text("stepspace")
        set_text("dirhold")
        set_text("dirsetup")
        set_text("maxferror")
        set_text("minferror")
        set_text("outputscale")
        set_value("outputoffset")
        set_active("invertmotor")
        set_active("invertencoder")  
        set_text("maxoutput")
        w["pulleynum"].set_text("%s" % d[axis+"pulleynum"])
        w["pulleyden"].set_text("%s" % d[axis +"pulleyden"])
        w["leadscrew"].set_text("%s" % d[axis +"leadscrew"])
        set_text("compfilename")
        set_active("comptype")
        set_value("backlash")
        set_active("usecomp")
        w["encoderline"].set_text("%d" % (d[axis+"encodercounts"]/4))
        #set_text("encodercounts")
        set_text("scale")
        w[axis+"maxvel"].set_text("%d" % (d[axis+"maxvel"]*60))
        set_text("maxacc")
        set_text("homepos")
        set_text("minlim")
        set_text("maxlim")
        set_text("homesw")
        w[axis+"homesearchvel"].set_text("%d" % (d[axis+"homesearchvel"]*60))
        w[axis+"homelatchvel"].set_text("%d" % (d[axis+"homelatchvel"]*60))
        w[axis+"homefinalvel"].set_text("%d" % (d[axis+"homefinalvel"]*60))
        set_active("searchdir")
        set_active("latchdir")
        set_active("usehomeindex")

        if axis == "a":
            w["leadscrewlabel"].set_text(_("Reduction Ratio"))
            w["screwunits"].set_text(_("degrees / rev"))
            w[axis + "velunits"].set_text(_("degrees / min"))
            w[axis + "accunits"].set_text(_("degrees / sec²"))
            w[axis + "homevelunits"].set_text(_("degrees / min"))
            w[axis + "homelatchvelunits"].set_text(_("degrees / min"))
            w[axis + "homefinalvelunits"].set_text(_("degrees / min"))
            w[axis + "accdistunits"].set_text(_("degrees"))
            if stepdriven:
                w[axis + "resolutionunits1"].set_text(_("degree / Step"))        
                w[axis + "scaleunits"].set_text(_("Steps / degree"))
            else:
                w[axis + "resolutionunits1"].set_text(_("degrees / encoder pulse"))
                w[axis + "scaleunits"].set_text(_("Encoder pulses / degree"))
            w[axis + "minfollowunits"].set_text(_("degrees"))
            w[axis + "maxfollowunits"].set_text(_("degrees"))

        elif d.units:
            w["leadscrewlabel"].set_text(_("Leadscrew Pitch"))
            w["screwunits"].set_text(_("(mm / rev)"))
            w[axis + "velunits"].set_text(_("mm / min"))
            w[axis + "accunits"].set_text(_("mm / sec²"))
            w[axis + "homevelunits"].set_text(_("mm / min"))
            w[axis + "homelatchvelunits"].set_text(_("mm / min"))
            w[axis + "homefinalvelunits"].set_text(_("mm / min"))
            w[axis + "accdistunits"].set_text(_("mm"))
            if stepdriven:
                w[axis + "resolutionunits1"].set_text(_("mm / Step"))        
                w[axis + "scaleunits"].set_text(_("Steps / mm"))
            else:
                w[axis + "resolutionunits1"].set_text(_("mm / encoder pulse"))          
                w[axis + "scaleunits"].set_text(_("Encoder pulses / mm"))
           
            w[axis + "minfollowunits"].set_text(_("mm"))
            w[axis + "maxfollowunits"].set_text(_("mm"))
           
        else:
            w["leadscrewlabel"].set_text(_("Leadscrew TPI"))
            w["screwunits"].set_text(_("(rev / inch)"))
            w[axis + "velunits"].set_text(_("inches / min"))
            w[axis + "accunits"].set_text(_("inches / sec²"))
            w[axis + "homevelunits"].set_text(_("inches / min"))
            w[axis + "homelatchvelunits"].set_text(_("inches / min"))
            w[axis + "homefinalvelunits"].set_text(_("inches / min"))
            w[axis + "accdistunits"].set_text(_("inches"))
            if stepdriven:
                w[axis + "resolutionunits1"].set_text(_("inches / Step"))        
                w[axis + "scaleunits"].set_text(_("Steps / inch"))
            else:
                w[axis + "resolutionunits1"].set_text(_("inches / encoder pulse"))        
                w[axis + "scaleunits"].set_text(_("Encoder pulses / inch"))
           
            w[axis + "minfollowunits"].set_text(_("inches"))
            w[axis + "maxfollowunits"].set_text(_("inches"))

        w[axis + "servo_info"].set_sensitive(not stepdriven)
        w[axis + "stepper_info"].set_sensitive(stepdriven)    
        w[axis + "drivertype"].set_active(self.drivertype_toindex(axis))
        if w[axis + "drivertype"].get_active_text()  == _("Custom"):
            w[axis + "steptime"].set_value(d[axis + "steptime"])
            w[axis + "stepspace"].set_value(d[axis + "stepspace"])
            w[axis + "dirhold"].set_value(d[axis + "dirhold"])
            w[axis + "dirsetup"].set_value(d[axis + "dirsetup"])
 
        thisaxishome = set(("all-home", "home-" + axis, "min-home-" + axis,"max-home-" + axis, "both-home-" + axis))
        homes = False
        for i in thisaxishome:
            test = self.data.findsignal(i)
            if not test == "false": homes = True
        w[axis + "homesw"].set_sensitive(homes)
        w[axis + "homesearchvel"].set_sensitive(homes)
        w[axis + "searchdir"].set_sensitive(homes)
        w[axis + "latchdir"].set_sensitive(homes)
        w[axis + "usehomeindex"].set_sensitive(homes)
        w[axis + "homefinalvel"].set_sensitive(homes)
        w[axis + "homelatchvel"].set_sensitive(homes)

        i = d[axis + "usecomp"]
        w[axis + "comptype"].set_sensitive(i)
        w[axis + "compfilename"].set_sensitive(i)
        i = d[axis + "usebacklash"]
        w[axis + "backlash"].set_sensitive(i)
      #  w[axis + "steprev"].grab_focus()
        gobject.idle_add(lambda: self.update_pps(axis))

    def on_xusecomp_toggled(self, *args): self.comp_toggle('x')
    def on_yusecomp_toggled(self, *args): self.comp_toggle('y')
    def on_zusecomp_toggled(self, *args): self.comp_toggle('z')
    def on_ausecomp_toggled(self, *args): self.comp_toggle('a')
    def on_xusebacklash_toggled(self, *args): self.backlash_toggle('x')
    def on_yusebacklash_toggled(self, *args): self.backlash_toggle('y')
    def on_zusebacklash_toggled(self, *args): self.backlash_toggle('z')
    def on_ausebacklash_toggled(self, *args): self.backlash_toggle('a')

    def on_xdrivertype_changed(self, *args): self.driver_changed('x')
    def on_ydrivertype_changed(self, *args): self.driver_changed('y')
    def on_zdrivertype_changed(self, *args): self.driver_changed('z')
    def on_adrivertype_changed(self, *args): self.driver_changed('a')
    def on_sdrivertype_changed(self, *args): self.driver_changed('s')

    def driver_changed(self, axis):
        d = self.data
        w = self.widgets
        v = w[axis + "drivertype"].get_active()
        if v < len(drivertypes):
            d = drivertypes[v]
            w[axis + "steptime"].set_value(d[2])
            w[axis + "stepspace"].set_value(d[3])
            w[axis + "dirhold"].set_value(d[4])
            w[axis + "dirsetup"].set_value(d[5])

            w[axis + "steptime"].set_sensitive(0)
            w[axis + "stepspace"].set_sensitive(0)
            w[axis + "dirhold"].set_sensitive(0)
            w[axis + "dirsetup"].set_sensitive(0)
        else:
            w[axis + "steptime"].set_sensitive(1)
            w[axis + "stepspace"].set_sensitive(1)
            w[axis + "dirhold"].set_sensitive(1)
            w[axis + "dirsetup"].set_sensitive(1)
        #self.on_calculate_ideal_period()

    def drivertype_toindex(self, axis, what=None):
        if what is None: what = self.data[axis + "drivertype"]
        for i, d in enumerate(drivertypes):
            if d[0] == what: return i
        return len(drivertypes)

    def drivertype_toid(self, axis, what=None):
        if not isinstance(what, int): what = self.drivertype_toindex(axis, what)
        if what < len(drivertypes): return drivertypes[what][0]
        return "custom"

    def drivertype_fromindex(self, axis):
        i = self.widgets[axis + "drivertype"].get_active()
        if i < len(drivertypes): return drivertypes[i][1]
        return _("Custom")

    def comp_toggle(self, axis):
        i = self.widgets[axis + "usecomp"].get_active()   
        self.widgets[axis + "compfilename"].set_sensitive(i)
        self.widgets[axis + "comptype"].set_sensitive(i)
        if i:
            self.widgets[axis + "backlash"].set_sensitive(0)
            self.widgets[axis + "usebacklash"].set_active(0)

    def backlash_toggle(self, axis):
        i = self.widgets[axis + "usebacklash"].get_active()   
        self.widgets[axis + "backlash"].set_sensitive(i)
        if i:
            self.widgets[axis + "compfilename"].set_sensitive(0)
            self.widgets[axis + "comptype"].set_sensitive(0)
            self.widgets[axis + "usecomp"].set_active(0)


    def axis_done(self, axis):
        d = self.data
        w = self.widgets
        def get_text(n): d[axis + n] = float(w[axis + n].get_text())
        def get_active(n): d[axis + n] = w[axis + n].get_active()
        d[axis + "steprev"] = int(w["steprev"].get_text())
        d[axis + "microstep"] = int(w["microstep"].get_text())
        get_text("P")
        get_text("I")
        get_text("D")
        get_text("FF0")
        get_text("FF1")
        get_text("FF2")
        get_text("bias")
        get_text("deadband")
        get_text("steptime")
        get_text("stepspace")
        get_text("dirhold")
        get_text("dirsetup")
        get_text("maxferror")
        get_text("minferror")
        get_text("outputscale")
        get_text("outputoffset")
        get_text("maxoutput")
        d[axis + "encodercounts"] = int(w["encoderline"].get_text())*4
        get_text("scale")
        get_active("invertmotor")
        get_active("invertencoder") 
        d[axis + "pulleynum"] = int(w["pulleynum"].get_text())
        d[axis + "pulleyden"] = int(w["pulleyden"].get_text())
        d[axis + "leadscrew"] = int(w["leadscrew"].get_text())
        d[axis + "compfilename"] = w[axis + "compfilename"].get_text()
        get_active("comptype")
        d[axis + "backlash"]= w[axis + "backlash"].get_value()
        get_active("usecomp")
        get_active("usebacklash")
        d[axis + "maxvel"] = (float(w[axis + "maxvel"].get_text())/60)
        get_text("maxacc")
        get_text("homepos")
        get_text("minlim")
        get_text("maxlim")
        get_text("homesw")
        d[axis + "homesearchvel"] = (float(w[axis + "homesearchvel"].get_text())/60)
        d[axis + "homelatchvel"] = (float(w[axis + "homelatchvel"].get_text())/60)
        d[axis + "homefinalvel"] = (float(w[axis + "homefinalvel"].get_text())/60)
        get_active("searchdir")
        get_active("latchdir")
        get_active("usehomeindex")
        d[axis + "drivertype"] = self.drivertype_toid(axis, w[axis + "drivertype"].get_active())

    def update_pps(self, axis):
        w = self.widgets
        d = self.data
        def get(n): return float(w[axis + n].get_text())

        try:
            #pitch = float(w["leadscrew"].get_text())
            #if d.units == 1 or axis =='a' : pitch = 1./pitch
            pps = (float(w[axis+"scale"].get_text()) * (get("maxvel")/60))
            if pps == 0: raise ValueError
            pps = abs(pps)
            w[axis + "hz"].set_text("%.1f" % pps)
            acctime = (get("maxvel")/60) / get("maxacc")
            accdist = acctime * .5 * (get("maxvel")/60)
            w[axis + "acctime"].set_text("%.4f" % acctime)
            if not axis == 's':
                w[axis + "accdist"].set_text("%.4f" % accdist)                 
            w[axis + "chartresolution"].set_text("%.7f" % (1.0 / float(w[axis+"scale"].get_text())))
            w[axis + "calscale"].set_text(w[axis+"scale"].get_text())
            self.widgets.druid1.set_buttons_sensitive(1,1,1,1)
            w[axis + "axistune"].set_sensitive(1)
        except (ValueError, ZeroDivisionError): # Some entries not numbers or not valid
            w[axis + "chartresolution"].set_text("")
            w[axis + "acctime"].set_text("")
            if not axis == 's':
                w[axis + "accdist"].set_text("")
            w[axis + "hz"].set_text("")
            w[axis + "calscale"].set_text("")
            self.widgets.druid1.set_buttons_sensitive(1,0,1,1)
            w[axis + "axistune"].set_sensitive(0)

    def on_spindle_info_changed(self, *args): self.update_pps('s')
        
    def on_xscale_changed(self, *args): self.update_pps('x')
    def on_yscale_changed(self, *args): self.update_pps('y')
    def on_zscale_changed(self, *args): self.update_pps('z')
    def on_ascale_changed(self, *args): self.update_pps('a')
    
    def on_xsteprev_changed(self, *args): self.update_pps('x')
    def on_ysteprev_changed(self, *args): self.update_pps('y')
    def on_zsteprev_changed(self, *args): self.update_pps('z')
    def on_asteprev_changed(self, *args): self.update_pps('a')

    def on_xmicrostep_changed(self, *args): self.update_pps('x')
    def on_ymicrostep_changed(self, *args): self.update_pps('y')
    def on_zmicrostep_changed(self, *args): self.update_pps('z')
    def on_amicrostep_changed(self, *args): self.update_pps('a')

    def on_xpulleynum_changed(self, *args): self.update_pps('x')
    def on_ypulleynum_changed(self, *args): self.update_pps('y')
    def on_zpulleynum_changed(self, *args): self.update_pps('z')
    def on_apulleynum_changed(self, *args): self.update_pps('a')

    def on_xencoderlines_changed(self, *args):self.update_pps('x')
    def on_yencoderlines_changed(self, *args):self.update_pps('y')
    def on_zencoderlines_changed(self, *args):self.update_pps('z')
    def on_aencoderlines_changed(self, *args):self.update_pps('a')
 
    def on_xpulleyden_changed(self, *args): self.update_pps('x')
    def on_ypulleyden_changed(self, *args): self.update_pps('y')
    def on_zpulleyden_changed(self, *args): self.update_pps('z')
    def on_apulleyden_changed(self, *args): self.update_pps('a')

    def on_xleadscrew_changed(self, *args): self.update_pps('x')
    def on_yleadscrew_changed(self, *args): self.update_pps('y')
    def on_zleadscrew_changed(self, *args): self.update_pps('z')
    def on_aleadscrew_changed(self, *args): self.update_pps('a')

    def on_xmaxvel_changed(self, *args): self.update_pps('x')
    def on_ymaxvel_changed(self, *args): self.update_pps('y')
    def on_zmaxvel_changed(self, *args): self.update_pps('z')
    def on_amaxvel_changed(self, *args): self.update_pps('a')

    def on_xmaxacc_changed(self, *args): self.update_pps('x')
    def on_ymaxacc_changed(self, *args): self.update_pps('y')
    def on_zmaxacc_changed(self, *args): self.update_pps('z')
    def on_amaxacc_changed(self, *args): self.update_pps('a')
        
    def on_xaxis_prepare(self, *args): self.axis_prepare('x')
    def on_yaxis_prepare(self, *args): self.axis_prepare('y')
    def on_zaxis_prepare(self, *args): self.axis_prepare('z')
    def on_aaxis_prepare(self, *args): self.axis_prepare('a')
   
    def on_xaxis_next(self, *args):
        self.axis_done('x')
        if self.data.axes == 2:
            self.widgets.druid1.set_page(self.widgets.zaxismotor)
            return True
        else:
            self.widgets.druid1.set_page(self.widgets.yaxismotor)
            return True
    def on_yaxis_next(self, *args):
        self.axis_done('y')
        self.widgets.druid1.set_page(self.widgets.zaxismotor)
        return True  
    def on_xaxis_back(self, *args):
        self.axis_done('x')
        self.widgets.druid1.set_page(self.widgets.xaxismotor)
        return True
    def on_yaxis_back(self, *args): 
        self.axis_done('y')
        self.widgets.druid1.set_page(self.widgets.yaxismotor)
        return True
    def on_zaxis_next(self, *args):
        self.axis_done('z')
        if self.data.axes != 1 :
            if self.has_spindle_speed_control():
                self.widgets.druid1.set_page(self.widgets.spindle)
                return True
            else:
                self.widgets.druid1.set_page(self.widgets.advanced)
                return True
        else:
            self.widgets.druid1.set_page(self.widgets.aaxismotor)
            return True
    def on_zaxis_back(self, *args):
        self.axis_done('z')     
        self.widgets.druid1.set_page(self.widgets.zaxismotor)
        return True
    def on_aaxis_next(self, *args):
        self.axis_done('a')
        if self.has_spindle_speed_control():
            self.widgets.druid1.set_page(self.widgets.spindle)
        else:
            self.widgets.druid1.set_page(self.widgets.advanced)
        return True
    def on_aaxis_back(self, *args):
        self.axis_done('a')
        self.widgets.druid1.set_page(self.widgets.aaxismotor)
        return True

    def on_xaxistest_clicked(self, *args): self.test_axis('x')
    def on_yaxistest_clicked(self, *args): self.test_axis('y')
    def on_zaxistest_clicked(self, *args): self.test_axis('z')
    def on_aaxistest_clicked(self, *args): self.test_axis('a')
    def on_saxistest_clicked(self, *args): self.test_axis('s')

    def on_xaxistune_clicked(self, *args): self.tune_axis('x')
    def on_yaxistune_clicked(self, *args): self.tune_axis('y')
    def on_zaxistune_clicked(self, *args): self.tune_axis('z')
    def on_aaxistune_clicked(self, *args): self.tune_axis('a')

    def on_spindle_prepare(self, *args):
        d = self.data
        w = self.widgets
        self.widgets.spidcontrol.set_active( self.data.spidcontrol )
        test = self.data.findsignal("s-stepgen-step")
        stepdriven = 1
        if test == "false":stepdriven = 0
        test = self.data.findsignal("s-pwm-pulse")
        pwmdriven = 1
        if test == "false":pwmdriven = 0
        def set_text(n): w[n].set_text("%s" % d[n])
        def set_value(n): w[n].set_value(d[n])
        def set_active(n): w[n].set_active(d[n])
        model = w["sdrivertype"].get_model()
        model.clear()
        for i in drivertypes:
            model.append((i[1],))
        model.append((_("Custom"),))
        
        if stepdriven:
            w["sresolutionunits"].set_text(_("revolution / Step"))        
            w["sscaleunits"].set_text(_("Steps / revolution"))
        else:
            w["sresolutionunits"].set_text(_("revolution / encoder pulse"))
            w["sscaleunits"].set_text(_("Encoder pulses / revolution"))
        w["leadscrewlabel"].set_text(_("Reduction Ratio"))
        #self.widgets['spindlecarrier'].set_text("%s" % self.data.spindlecarrier)
        w['spindlespeed1'].set_text("%s" % d.spindlespeed1)
        w['spindlespeed2'].set_text("%s" % d.spindlespeed2)
        w['spindlepwm1'].set_text("%s" % d.spindlepwm1)
        w['spindlepwm2'].set_text("%s" % d.spindlepwm2)
        #self.widgets['spindlecpr'].set_text("%s" % self.data.spindlecpr)
        has_spindle_pha = self.data.findsignal("s-encoder-a")
        if has_spindle_pha == "false":
            w.sencoderlines.set_sensitive(0)
            w.sencodercounts.set_sensitive(0)
        else: 
            w.sencoderlines.set_sensitive(1) 
            w.sencodercounts.set_sensitive(1) 
        w["soutputscale"].set_sensitive(pwmdriven)
        w["soutputoffset"].set_sensitive(pwmdriven)
        w["smaxoutput"].set_sensitive(pwmdriven)
        w["sservo_info"].set_sensitive(pwmdriven)
        self.on_spidcontrol_toggled()
        w["saxistest"].set_sensitive(pwmdriven)
        w["sstepper_info"].set_sensitive(stepdriven)    
        w["sdrivertype"].set_active(self.drivertype_toindex('s')) 
        
        w["steprev"].set_text("%s" % d["ssteprev"])
        w["microstep"].set_text("%s" % d["smicrostep"])
        set_value("sP")
        set_value("sI")
        set_value("sD")
        set_value("sFF0")
        set_value("sFF1")
        set_value("sFF2")
        set_text("sbias")
        set_text("sdeadband")
        set_text("ssteptime")
        set_text("sstepspace")
        set_text("sdirhold")
        set_text("sdirsetup")
        set_text("soutputscale")
        set_text("soutputoffset")
        set_active("sinvertmotor")
        set_active("sinvertencoder")  
        set_text("smaxoutput")
        set_text("sscale")
        w["pulleynum"].set_text("%s" % d["spulleynum"])
        w["pulleyden"].set_text("%s" % d["spulleyden"])
        w["leadscrew"].set_text("%s" % d["sleadscrew"])
        w["sencoderlines"].set_text("%d" % (d["sencodercounts"]/4))
        set_text("sencodercounts")
        w["smaxvel"].set_text("%d" % (d["smaxvel"]*60))
        set_text("smaxacc")
        
    def on_spindle_next(self, *args):
        d = self.data
        w = self.widgets 
        def get_text(n): d["s" + n] = float(w["s" + n].get_text())
        def get_active(n): d["s" + n] = w["s" + n].get_active()
        d["ssteprev"] = int(w["steprev"].get_text())
        d["smicrostep"] = int(w["microstep"].get_text())
        get_text("P")
        get_text("I")
        get_text("D")
        get_text("FF0")
        get_text("FF1")
        get_text("FF2")
        get_text("bias")
        get_text("deadband")
        get_text("steptime")
        get_text("stepspace")
        get_text("dirhold")
        get_text("dirsetup")        
        get_text("outputscale")
        get_text("outputoffset")
        get_text("maxoutput")
        get_text("encodercounts")
        get_active("invertmotor")
        get_active("invertencoder")
        get_text("scale")
        get_active("pidcontrol")  
        d["spulleynum"] = int(w["pulleynum"].get_text())
        d["spulleyden"] = int(w["pulleyden"].get_text())
        d["sleadscrew"] = int(w["leadscrew"].get_text())
        d["smaxvel"] = (float(w["smaxvel"].get_text())/60)
        get_text("maxacc")
        
        d["sdrivertype"] = self.drivertype_toid('s', w["sdrivertype"].get_active())
        #self.data.spindlecarrier = float(self.widgets.spindlecarrier.get_text())
        self.data.spindlespeed1 = float(self.widgets.spindlespeed1.get_text())
        self.data.spindlespeed2 = float(self.widgets.spindlespeed2.get_text())
        self.data.spindlepwm1 = float(self.widgets.spindlepwm1.get_text())
        self.data.spindlepwm2 = float(self.widgets.spindlepwm2.get_text())
        #self.data.spindlecpr = float(self.widgets.spindlecpr.get_text())
        
    def on_spindle_back(self, *args):
        self.on_spindle_next()
        if self.data.axes != 1:
            self.widgets.druid1.set_page(self.widgets.zaxis)
        else:
            self.widgets.druid1.set_page(self.widgets.aaxis)
        return True

    def has_spindle_speed_control(self):
        for test in ("s-stepgen-step", "s-pwm-pulse", "s-encoder-a", "spindle-enable", "spindle-cw", "spindle-ccw", "spindle-brake"):
            has_spindle = self.data.findsignal(test)
            if not has_spindle == "false":
                return True
        return False

    def on_spidcontrol_toggled(self, *args):
        test = self.data.findsignal("s-pwm-pulse")
        pwmdriven = 1
        if test == "false":pwmdriven = 0
        if self.widgets.spidcontrol.get_active() == False: pwmdriven = 0
        self.widgets.sP.set_sensitive(pwmdriven)
        self.widgets.sI.set_sensitive(pwmdriven)
        self.widgets.sD.set_sensitive(pwmdriven)
        self.widgets.sFF0.set_sensitive(pwmdriven)
        self.widgets.sFF1.set_sensitive(pwmdriven)
        self.widgets.sFF2.set_sensitive(pwmdriven)
        self.widgets.sbias.set_sensitive(pwmdriven)
        self.widgets.sdeadband.set_sensitive(pwmdriven)
       


    def on_advanced_prepare(self, *args):       
        self.data.help = "help-advanced.txt"
        self.widgets.classicladder.set_active(self.data.classicladder)
        self.widgets.modbus.set_active(self.data.modbus)
        self.widgets.digitsin.set_value(self.data.digitsin)
        self.widgets.digitsout.set_value(self.data.digitsout)
        self.widgets.s32in.set_value(self.data.s32in)
        self.widgets.s32out.set_value(self.data.s32out)
        self.widgets.floatsin.set_value(self.data.floatsin)
        self.widgets.floatsout.set_value(self.data.floatsout)
        self.widgets.halui.set_active(self.data.halui)
        self.on_halui_toggled()
        for i in range(1,16):
            self.widgets["halui_cmd"+str(i)].set_text(self.data["halui_cmd"+str(i)])  
        self.widgets.ladderconnect.set_active(self.data.ladderconnect)      
        self.on_classicladder_toggled()
        if  not self.widgets.createconfig.get_active():
           if os.path.exists(os.path.expanduser("~/emc2/configs/%s/custom.clp" % self.data.machinename)):
                self.widgets.ladderexist.set_active(True)

    def on_advanced_next(self, *args):
         
        self.data.classicladder = self.widgets.classicladder.get_active()
        self.data.modbus = self.widgets.modbus.get_active()
        self.data.digitsin = self.widgets.digitsin.get_value()
        self.data.digitsout = self.widgets.digitsout.get_value()
        self.data.s32in = self.widgets.s32in.get_value()
        self.data.s32out = self.widgets.s32out.get_value()
        self.data.floatsin = self.widgets.floatsin.get_value()
        self.data.floatsout = self.widgets.floatsout.get_value()
        self.data.halui = self.widgets.halui.get_active() 
        for i in range(1,16):
            self.data["halui_cmd"+str(i)] = self.widgets["halui_cmd"+str(i)].get_text()   
        
        self.data.ladderconnect = self.widgets.ladderconnect.get_active()          
        if self.data.classicladder:
           if self.widgets.ladderblank.get_active() == True:
              if self.data.tempexists:
                   self.data.laddername='TEMP.clp'
              else:
                   self.data.laddername= 'blank.clp'
                   self.data.ladderhaltype = 0
           if self.widgets.ladder1.get_active() == True:
              self.data.laddername = 'estop.clp'
              has_estop = self.data.findsignal("estop-ext")
              if has_estop == "false":
                 self.warning_dialog(_("You need to designate an E-stop input pin for this ladder program."),True)
                 self.widgets.druid1.set_page(self.widgets.advanced)
                 return True
              self.data.ladderhaltype = 1
           if self.widgets.ladder2.get_active() == True:
                 self.data.laddername = 'serialmodbus.clp'
                 self.data.modbus = 1
                 self.widgets.modbus.set_active(self.data.modbus) 
                 self.data.ladderhaltype = 0          
           if self.widgets.ladderexist.get_active() == True:
              self.data.laddername='custom.clp'
           else:
               if os.path.exists(os.path.expanduser("~/emc2/configs/%s/custom.clp" % self.data.machinename)):
                  if not self.warning_dialog(_("OK to replace existing custom ladder program?\nExisting Custom.clp will be renamed custom_backup.clp.\nAny existing file named -custom_backup.clp- will be lost. "),False):
                     self.widgets.druid1.set_page(self.widgets.advanced)
                     return True 
           if self.widgets.ladderexist.get_active() == False:
              if os.path.exists(os.path.join(distdir, "configurable_options/ladder/TEMP.clp")):
                 if not self.warning_dialog(_("You edited a ladder program and have selected a different program to copy to your configuration file.\nThe edited program will be lost.\n\nAre you sure?  "),False):
                   self.widgets.druid1.set_page(self.widgets.advanced)
                   return True       
        

    def on_advanced_back(self, *args):
        if self.has_spindle_speed_control():
            self.widgets.druid1.set_page(self.widgets.spindle)
        elif self.data.axes != 1:
            self.widgets.druid1.set_page(self.widgets.zaxis)
        else:
            self.widgets.druid1.set_page(self.widgets.aaxis)
        return True

    def on_loadladder_clicked(self, *args):self.load_ladder(self)
 
    def on_halui_toggled(self, *args):
        if not self.data.nojogbuttons:
            self.widgets.halui.set_active(1)
            self.widgets.halui.set_sensitive(0)
            self.widgets.haluitable.set_sensitive(1)
        else:
            i= self.widgets.halui.get_active()
            self.widgets.haluitable.set_sensitive(i)

    def on_classicladder_toggled(self, *args):

        i= self.widgets.classicladder.get_active()
        self.widgets.digitsin.set_sensitive(i)
        self.widgets.digitsout.set_sensitive(i)
        self.widgets.s32in.set_sensitive(i)
        self.widgets.s32out.set_sensitive(i)
        self.widgets.floatsin.set_sensitive(i)
        self.widgets.floatsout.set_sensitive(i)
        self.widgets.modbus.set_sensitive(i)
        self.widgets.ladderblank.set_sensitive(i)
        self.widgets.ladder1.set_sensitive(i)
        self.widgets.ladder2.set_sensitive(i)
        if  self.widgets.createconfig.get_active():
            self.widgets.ladderexist.set_sensitive(False)
        else:
            self.widgets.ladderexist.set_sensitive(i)
        self.widgets.loadladder.set_sensitive(i)
        self.widgets.label_digin.set_sensitive(i)
        self.widgets.label_digout.set_sensitive(i)
        self.widgets.label_s32in.set_sensitive(i)
        self.widgets.label_s32out.set_sensitive(i)
        self.widgets.label_floatin.set_sensitive(i)
        self.widgets.label_floatout.set_sensitive(i)
        self.widgets.ladderconnect.set_sensitive(i)
        

    def on_pyvcp_toggled(self,*args):
        i= self.widgets.pyvcp.get_active()
        self.widgets.pyvcpblank.set_sensitive(i)
        self.widgets.pyvcp1.set_sensitive(i)
        self.widgets.pyvcp2.set_sensitive(i)
        self.widgets.pyvcpgeometry.set_sensitive(i)
        if  self.widgets.createconfig.get_active():
            self.widgets.pyvcpexist.set_sensitive(False)
        else:
            self.widgets.pyvcpexist.set_sensitive(i)
        self.widgets.displaypanel.set_sensitive(i)
        self.widgets.pyvcpconnect.set_sensitive(i)

    def on_displaypanel_clicked(self,*args):
        self.testpanel(self)

    def on_realtime_components_prepare(self,*args):
        self.data.help = "help-realtime.txt"
        self.widgets.userneededpid.set_value(self.data.userneededpid)
        if not self.intrnldata.components_is_prepared:
            textbuffer = self.widgets.loadcompservo.get_buffer()
            for i in self.data.loadcompservo:
                if i == '': continue
                textbuffer.insert_at_cursor(i+"\n" )
            textbuffer = self.widgets.addcompservo.get_buffer()
            for i in self.data.addcompservo:
                if i == '': continue
                textbuffer.insert_at_cursor(i+"\n" )
            textbuffer = self.widgets.loadcompbase.get_buffer()
            for i in self.data.loadcompbase:
               textbuffer.insert_at_cursor(i+"\n" )
            textbuffer = self.widgets.addcompbase.get_buffer()
            for i in self.data.addcompbase:
                if i == '': continue
                textbuffer.insert_at_cursor(i+"\n" )
            self.intrnldata.components_is_prepared = True

    def on_realtime_components_next(self,*args):
        self.data.userneededpid = self.widgets.userneededpid.get_value()
        
        textbuffer = self.widgets.loadcompservo.get_buffer()
        startiter = textbuffer.get_start_iter()
        enditer = textbuffer.get_end_iter()
        test = textbuffer.get_text(startiter,enditer)
        i = test.split('\n')
        print "loadcompservo ",i
        self.data.loadcompservo = i
        textbuffer = self.widgets.addcompservo.get_buffer()
        startiter = textbuffer.get_start_iter()
        enditer = textbuffer.get_end_iter()
        test = textbuffer.get_text(startiter,enditer)
        i = test.split('\n')
        print "addcompservo ",i
        self.data.addcompservo = i
        textbuffer = self.widgets.loadcompbase.get_buffer()
        startiter = textbuffer.get_start_iter()
        enditer = textbuffer.get_end_iter()
        test = textbuffer.get_text(startiter,enditer)
        i = test.split('\n')
        print "loadcompbase ",i
        self.data.loadcompbase = i
        textbuffer = self.widgets.addcompbase.get_buffer()
        startiter = textbuffer.get_start_iter()
        enditer = textbuffer.get_end_iter()
        test = textbuffer.get_text(startiter,enditer)
        i = test.split('\n')
        print "addcompbase ",i
        self.data.addcompbase = i

    def on_complete_back(self, *args):
        self.widgets.druid1.set_page(self.widgets.advanced)
        return True
   
    def on_complete_finish(self, *args):
        # if parallel ports not used clear all signals
        parportnames = ("pp1","pp2","pp3")
        for check,connector in enumerate(parportnames):
            if self.data.number_pports >= (check+1):continue
            # initialize parport input / inv pins
            for i in (1,2,3,4,5,6,7,8,10,11,12,13,15):
                pinname ="%sIpin%d"% (connector,i)
                self.data[pinname] = UNUSED_INPUT
                pinname ="%sIpin%dinv"% (connector,i)
                self.data[pinname] = False
            # initialize parport output / inv pins
            for i in (1,2,3,4,5,6,7,8,9,14,16,17):
                pinname ="%sOpin%d"% (connector,i)
                self.data[pinname] = UNUSED_OUTPUT
                pinname ="%sOpin%dinv"% (connector,i)
                self.data[pinname] = False
          
        # if mesa card not used clear all signals
        if self.data.mesa5i20 == 0:
            for connector in(2,3,4,5):
                # This initializes GPIO input pins
                for i in range(0,16):
                    pinname ="m5i20c%dpin%d"% (connector,i)
                    self.data[pinname] = UNUSED_INPUT
                    pinname ="m5i20c%dpin%dtype"% (connector,i)
                    self.data[pinname] = GPIOI
                # This initializes GPIO output pins
                for i in range(16,24):
                    pinname ="m5i20c%dpin%d"% (connector,i)
                    self.data[pinname] = UNUSED_OUTPUT
                    pinname ="m5i20c%dpin%dtype"% (connector,i)
                    self.data[pinname] = GPIOO
                # This initializes the mesa inverse pins
                for i in range(0,24):
                    pinname ="m5i20c%dpin%dinv"% (connector,i)
                    self.data[pinname] = False

        self.data.save()        
        if self.data.classicladder: 
           if not self.data.laddername == "custom.clp":
                filename = os.path.join(distdir, "configurable_options/ladder/%s" % self.data.laddername)
                original = os.path.expanduser("~/emc2/configs/%s/custom.clp" % self.data.machinename)
                if os.path.exists(filename):     
                  if os.path.exists(original):
                     print "custom file already exists"
                     shutil.copy( original,os.path.expanduser("~/emc2/configs/%s/custom_backup.clp" % self.data.machinename) ) 
                     print "made backup of existing custom"
                  shutil.copy( filename,original)
                  print "copied ladder program to usr directory"
                  print"%s" % filename
                else:
                     print "Master or temp ladder files missing from configurable_options dir"

        if self.data.pyvcp and not self.widgets.pyvcpexist.get_active() == True:                
           panelname = os.path.join(distdir, "configurable_options/pyvcp/%s" % self.data.pyvcpname)
           originalname = os.path.expanduser("~/emc2/configs/%s/custompanel.xml" % self.data.machinename)
           if os.path.exists(panelname):     
                  if os.path.exists(originalname):
                     print "custom PYVCP file already exists"
                     shutil.copy( originalname,os.path.expanduser("~/emc2/configs/%s/custompanel_backup.xml" % self.data.machinename) ) 
                     print "made backup of existing custom"
                  shutil.copy( panelname,originalname)
                  print "copied PYVCP program to usr directory"
                  print"%s" % panelname
           else:
                  print "Master PYVCP files missing from configurable_options dir"
        gtk.main_quit()

    def on_calculate_ideal_period(self, *args):
        steptime = self.widgets.steptime.get_value()
        stepspace = self.widgets.stepspace.get_value()
        latency = self.widgets.latency.get_value()
        minperiod = self.data.minperiod(steptime, stepspace, latency)
        maxhz = int(1e9 / minperiod)
        if not self.data.doublestep(steptime): maxhz /= 2
        self.widgets.baseperiod.set_text("%d ns" % minperiod)
        self.widgets.maxsteprate.set_text("%d Hz" % maxhz)

    def on_latency_test_clicked(self, w):
        self.latency_pid = os.spawnvp(os.P_NOWAIT,
                                "latency-test", ["latency-test"])
        self.widgets['window1'].set_sensitive(0)
        gobject.timeout_add(1, self.latency_running_callback)

    def latency_running_callback(self):
        pid, status = os.waitpid(self.latency_pid, os.WNOHANG)
        if pid:
            self.widgets['window1'].set_sensitive(1)
            return False
        return True

    def m5i20test(self,w):
        board = self.data.mesa_currentfirmwaredata[0]
        firmware = self.data.mesa_currentfirmwaredata[1]   
        print "-%s-%s-"% (firmware,  self.data.mesa_firmware)      
        if board in( "5i22", "7i43"):
            self.warning_dialog( _(" The test panel for this board and/or firmware should work fine for GPIO but maybe not so fine for other components.\n work in progress. \n You must have the board installed for it to work.") , True)  

        #self.widgets['window1'].set_sensitive(0)
        panelname = os.path.join(distdir, "configurable_options/pyvcp")
        #self.terminal = terminal = os.popen("gnome-terminal --title=joystick_search -x less /proc/bus/input/devices", "w" )  
        self.halrun = halrun = os.popen("cd %(panelname)s\nhalrun -sf > /dev/null"% {'panelname':panelname,}, "w" )   
        halrun.write("loadrt threads period1=200000 name1=fast fp1=0 period2=1000000 name2=slow\n")
        halrun.write("loadrt hostmot2\n")
        halrun.write("""loadrt hm2_pci config="firmware=hm2-trunk/%s/%s.BIT num_encoders=%d num_pwmgens=%d num_stepgens=%d"\n"""
         % (board, firmware, self.data.numof_mesa_encodergens,
            self.data.numof_mesa_pwmgens, self.data.numof_mesa_stepgens ))
        halrun.write("loadrt or2 count=72\n")
        halrun.write("addf hm2_%s.0.read slow\n"% board)
        for i in range(0,72):
            halrun.write("addf or2.%d slow\n"% i)
        halrun.write("addf hm2_%s.0.write slow\n"% board)
        halrun.write("addf hm2_%s.0.pet_watchdog fast\n"% board)
        halrun.write("start\n")
        halrun.write("loadusr -Wn m5i20test pyvcp -g +700+0 -c m5i20test %(panel)s\n" %{'panel':"m5i20panel.xml",})
        halrun.write("loadusr halmeter -g 0 500\n")
        halrun.write("loadusr halmeter -g 0 620\n")
        
        for concount,connector in enumerate(self.data.mesa_currentfirmwaredata[11]) :
            for pin in range (0,24):
                firmptype,compnum = self.data.mesa_currentfirmwaredata[12+pin+(concount*24)]
                pinv = 'm5i20c%(con)dpin%(num)dinv' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}
                pintype = self.widgets[ptype].get_active_text()
                pininv = self.widgets[pinv].get_active()
                truepinnum = (concount*24) + pin
                # for output / open drain pins
                if  pintype in (GPIOO,GPIOD):                
                    halrun.write("setp m5i20test.led.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.button.%d.disable false\n"% truepinnum )
                    halrun.write("setp hm2_%s.0.gpio.%03d.is_output true\n"% (board,truepinnum ))
                    if pininv:  halrun.write("setp hm2_%s.0.gpio.%03d.invert_output true\n"% (board,truepinnum ))
                    halrun.write("net signal_out%d or2.%d.out hm2_%s.0.gpio.%03d.out\n"% (truepinnum,truepinnum,board,truepinnum))
                    halrun.write("net pushbutton.%d or2.%d.in1 m5i20test.button.%d\n"% (truepinnum,truepinnum,truepinnum))
                    halrun.write("net latchbutton.%d or2.%d.in0 m5i20test.checkbutton.%d\n"% (truepinnum,truepinnum,truepinnum))
                # for input pins
                elif pintype == GPIOI:                                    
                    halrun.write("setp m5i20test.button.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.led.%d.disable false\n"% truepinnum )
                    if pininv:  halrun.write("net blue_in%d hm2_%s.0.gpio.%03d.in_not m5i20test.led.%d\n"% (truepinnum,board,truepinnum,truepinnum))
                    else:   halrun.write("net blue_in%d hm2_%s.0.gpio.%03d.in m5i20test.led.%d\n"% (truepinnum,board,truepinnum,truepinnum))
                # for encoder pins
                elif pintype in (ENCA,ENCB,ENCI,ENCM):
                    halrun.write("setp m5i20test.led.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.button.%d.disable true\n"% truepinnum )                   
                    if not pintype == ENCA: continue                 
                    if pin == 3 :encpinnum = (connector-2)*4 
                    elif pin == 1 :encpinnum = 1+((connector-2)*4) 
                    elif pin == 15 :encpinnum = 2+((connector-2)*4) 
                    elif pin == 13 :encpinnum = 3+((connector-2)*4) 
                    halrun.write("setp m5i20test.enc.%d.reset.disable false\n"% encpinnum )
                    halrun.write("net yellow_reset%d hm2_%s.0.encoder.%02d.reset m5i20test.enc.%d.reset\n"% (encpinnum,board,encpinnum,encpinnum))
                    halrun.write("net yellow_count%d hm2_%s.0.encoder.%02d.count m5i20test.number.%d\n"% (encpinnum,board,encpinnum,encpinnum))
                # for PWM pins
                elif pintype in (PWMP,PWMD,PWME,PDMP,PDMD,PDME):
                    halrun.write("setp m5i20test.led.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.button.%d.disable true\n"% truepinnum )
                    if not pintype in (PWMP,PDMP): continue    
                    if pin == 7 :encpinnum = (connector-2)*4 
                    elif pin == 6 :encpinnum = 1 + ((connector-2)*4) 
                    elif pin == 19 :encpinnum = 2 + ((connector-2)*4) 
                    elif pin == 18 :encpinnum = 3 + ((connector-2)*4)        
                    halrun.write("net green_enable%d hm2_%s.0.pwmgen.%02d.enable m5i20test.dac.%d.enbl\n"% (encpinnum,board,encpinnum,encpinnum)) 
                    halrun.write("net green_value%d hm2_%s.0.pwmgen.%02d.value m5i20test.dac.%d-f\n"% (encpinnum,board,encpinnum,encpinnum)) 
                    halrun.write("setp hm2_%s.0.pwmgen.%02d.scale 10\n"% (board,encpinnum)) 
                # for Stepgen pins
                elif pintype in (STEPA,STEPB):
                    halrun.write("setp m5i20test.led.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.button.%d.disable true\n"% truepinnum ) 
                    if not pintype == STEPA : continue 
                    
                    halrun.write("net brown_enable%d hm2_%s.0.stepgen.%02d.enable m5i20test.step.%d.enbl\n"% (compnum,board,compnum,compnum))
                    halrun.write("net brown_value%d hm2_%s.0.stepgen.%02d.position-cmd m5i20test.anaout.%d\n"% (compnum,board,compnum,compnum))
                    halrun.write("setp hm2_%s.0.stepgen.%02d.maxaccel 0 \n"% (board,compnum))
                    halrun.write("setp hm2_%s.0.stepgen.%02d.maxvel 0 \n"% (board,compnum))
                else: 
                    print "pintype error IN mesa test panel method %s"% pintype
        if not board == "5i22":
                for pin in range (0,24):
                    truepinnum = (72) + pin
                    halrun.write("setp m5i20test.led.%d.disable true\n"% truepinnum )
                    halrun.write("setp m5i20test.button.%d.disable true\n"% truepinnum )
                for pin in range (8,12):
                    halrun.write("setp m5i20test.enc.%d.reset.disable true\n"% pin )
        halrun.write("waitusr m5i20test\n"); halrun.flush()
        halrun.close()
        #terminal.close()
        self.widgets['window1'].set_sensitive(1)

    def on_address_search_clicked(self,w):   
        match =  os.popen('lspci -v').read()
        self.widgets.helpwindow.set_title(_("PCI Board Info Search"))
        textbuffer = self.widgets.helpview.get_buffer()
        try :         
            textbuffer.set_text(match)
            self.widgets.helpwindow.show_all()
        except:
            text = _("PCI search page is unavailable\n")
            self.warning_dialog(text,True)

    def parporttest(self,w):
        panelname = os.path.join(distdir, "configurable_options/pyvcp")
        self.halrun = halrun = os.popen("cd %(panelname)s\nhalrun -sf > /dev/null"% {'panelname':panelname,}, "w" )  
        halrun.write("loadrt threads period1=100000 name1=fast fp1=0 period2=%d name2=slow\n"% self.data.servoperiod)
        halrun.write("loadrt probe_parport\n")
        if self.data.number_pports>0:
            port3name = port2name = port1name = port3dir = port2dir = port1dir = ""
            if self.data.number_pports>2:
                 port3name = " " + self.ioaddr3
                 if self.data.pp3_direction:
                    port3dir =" out"
                 else: 
                    port3dir =" in"
            if self.data.number_pports>1:
                 port2name = " " + self.data.ioaddr2
                 if self.data.pp2_direction:
                    port2dir =" out"
                 else: 
                    port2dir =" in"
            port1name = self.data.ioaddr
            if self.data.pp1_direction:
               port1dir =" out"
            else: 
               port1dir =" in"
            halrun.write( "loadrt hal_parport cfg=\"%s%s%s%s%s%s\"\n" % (port1name, port1dir, port2name, port2dir, port3name, port3dir))
        halrun.write("loadrt or2 count=12\n")
        if self.data.number_pports > 0:
            halrun.write( "addf parport.0.read fast\n")
        if self.data.number_pports > 1:
            halrun.write("addf parport.1.read fast\n")
        if self.data.number_pports > 2:
            halrun.write("addf parport.2.read fast\n")
        for i in range(0,12):
            halrun.write("addf or2.%d fast\n"% i)
        if self.data.number_pports > 0:
            halrun.write( "addf parport.0.write fast\n")
        if self.data.number_pports > 1:
            halrun.write("addf parport.1.write fast\n")
        if self.data.number_pports > 2:
            halrun.write("addf parport.2.write fast\n")
        halrun.write("loadusr -Wn parporttest pyvcp -c parporttest %(panel)s\n" %{'panel':"parportpanel.xml\n",})
        halrun.write("loadusr halmeter\n")
        templist = ("pp1","pp2","pp3")
        for j, k in enumerate(templist):
            if self.data.number_pports < (j+1): break 
            if self.data[k+"_direction"] == 1:
                inputpins = (10,11,12,13,15)
                outputpins = (1,2,3,4,5,6,7,8,9,14,16,17)               
                for x in (2,3,4,5,6,7,8,9):
                    halrun.write( "setp parporttest.%s_led.%d.disable true\n"%(k, x))
                    halrun.write( "setp parporttest.%s_led_text.%d.disable true\n"%(k, x))
            else:
                inputpins = (2,3,4,5,6,7,8,9,10,11,12,13,15)
                outputpins = (1,14,16,17)
                for x in (2,3,4,5,6,7,8,9):
                    halrun.write( "setp parporttest.%s_button.%d.disable true\n"% (k, x))
                    halrun.write( "setp parporttest.%s_button_text.%d.disable true\n"% (k, x))
            for x in inputpins: 
                i = self.data["%sIpin%dinv" % (k, x)]
                if i:  halrun.write( "net red_in_not.%d parporttest.%s_led.%d <= parport.%d.pin-%02d-in-not\n" % (x, k, x, j, x))
                else:  halrun.write( "net red_in.%d parporttest.%s_led.%d <= parport.%d.pin-%02d-in\n" % (x, k, x, j , x))               
                         
            for num, x in enumerate(outputpins):  
                i = self.data["%sOpin%dinv" % (k, x)]
                if i:  halrun.write( "setp parport.%d.pin-%02d-out-invert true\n" %(j, x))
                halrun.write("net signal_out%d or2.%d.out parport.%d.pin-%02d-out\n"% (x, num, j, x))
                halrun.write("net pushbutton.%d or2.%d.in1 parporttest.%s_button.%d\n"% (x, num, k, x))
                halrun.write("net latchbutton.%d or2.%d.in0 parporttest.%s_checkbutton.%d\n"% (x, num, k, x))

            
        halrun.write("start\n")
        halrun.write("waitusr parporttest\n"); halrun.flush()
        halrun.close()
        #terminal.close()
        self.widgets['window1'].set_sensitive(1)

    def testpanel(self,w):
        pos = "+0+0"
        size = ""
        panelname = os.path.join(distdir, "configurable_options/pyvcp")
        if self.widgets.pyvcpblank.get_active() == True:
           return True
        if self.widgets.pyvcp1.get_active() == True:
           panel = "spindle.xml"
        if self.widgets.pyvcp2.get_active() == True:
           panel = "xyzjog.xml"
        if self.widgets.pyvcpexist.get_active() == True:
           panel = "custompanel.xml"
           panelname = os.path.expanduser("~/emc2/configs/%s" % self.data.machinename)
        if self.widgets.pyvcpposcheckbutton.get_active() == True:
            xpos = self.widgets.pyvcpxpos.get_value()
            ypos = self.widgets.pyvcpypos.get_value()
            pos = "+%d+%d"% (xpos,ypos)
        if self.widgets.pyvcpsizecheckbutton.get_active() == True:
            width = self.widgets.pyvcpwidth.get_value()
            height = self.widgets.pyvcpheight.get_value()
            size = "%dx%d"% (width,height)
        
        self.halrun = halrun = os.popen("cd %(panelname)s\nhalrun -sf > /dev/null"% {'panelname':panelname,}, "w" )    
        halrun.write("loadusr -Wn displaytest pyvcp -g %(size)s%(pos)s -c displaytest %(panel)s\n" %{'size':size,'pos':pos,'panel':panel,})
        if self.widgets.pyvcp1.get_active() == True:
                halrun.write("setp displaytest.spindle-speed 1000\n")
                #halrun.write("setp displaytest.toolnumber 4\n")
        halrun.write("waitusr displaytest\n"); halrun.flush()
        halrun.close()

    def load_ladder(self,w):   
        newfilename = os.path.join(distdir, "configurable_options/ladder/TEMP.clp")    
        self.data.modbus = self.widgets.modbus.get_active()
        self.halrun = halrun = os.popen("halrun -sf > /dev/null", "w")
        halrun.write(""" 
              loadrt classicladder_rt numPhysInputs=%(din)d numPhysOutputs=%(dout)d numS32in=%(sin)d numS32out=%(sout)d numFloatIn=%(fin)d numFloatOut=%(fout)d\n""" % {
                      'din': self.widgets.digitsin.get_value(),
                      'dout': self.widgets.digitsout.get_value(),
                      'sin': self.widgets.s32in.get_value(),
                      'sout': self.widgets.s32out.get_value(), 
                      'fin':self.widgets.floatsin.get_value(),
                      'fout':self.widgets.floatsout.get_value(),
                 })
        if self.widgets.ladderexist.get_active() == True:
            if self.data.tempexists:
               self.data.laddername='TEMP.clp'
            else:
               self.data.laddername= 'blank.clp'
        if self.widgets.ladder1.get_active() == True:
            self.data.laddername= 'estop.clp'
        if self.widgets.ladder2.get_active() == True:
            self.data.laddername = 'serialmodbus.clp'
            self.data.modbus = True
            self.widgets.modbus.set_active(self.data.modbus)
        if self.widgets.ladderexist.get_active() == True:
            self.data.laddername='custom.clp'
            originalfile = filename = os.path.expanduser("~/emc2/configs/%s/custom.clp" % self.data.machinename)
        else:
            filename = os.path.join(distdir, "configurable_options/ladder/"+ self.data.laddername)        
        if self.data.modbus == True: 
            halrun.write("loadusr -w classicladder --modmaster --newpath=%(newfilename)s %(filename)s\n" %          { 'newfilename':newfilename ,'filename':filename })
        else:
            halrun.write("loadusr -w classicladder --newpath=%(newfilename)s %(filename)s\n" % { 'newfilename':newfilename ,'filename':filename })
        halrun.write("start\n"); halrun.flush()
        halrun.close()
        if os.path.exists(newfilename):
            self.data.tempexists = True
            self.widgets.newladder.set_text('Edited ladder program')
            self.widgets.ladderexist.set_active(True)
        else:
            self.data.tempexists = 0
        
    def tune_axis(self, axis):
        d = self.data
        w = self.widgets
        axnum = "xyza".index(axis)
        self.axis_under_tune = axis
        board = self.data.mesa_currentfirmwaredata[0]
        firmware = self.data.mesa_currentfirmwaredata[1]
        w.notebook2.set_current_page(axnum)
        stepgen = self.data.stepgen_sig(axis)
        print axis,stepgen
        if not stepgen == "false":
            w[axis+"tuningnotebook"].set_current_page(1)
            w[axis+"pid"].set_sensitive(0)
        else:
            w[axis+"tuningnotebook"].set_current_page(0)
            w[axis+"step"].set_sensitive(0)
            text = _("Servo tuning is not finished / working\n")
            self.warning_dialog(text,True)

        if axis == "a":
            w[axis + "tunedistunits"].set_text(_("degrees"))
            w[axis + "tunevelunits"].set_text(_("degrees / minute"))
            w[axis + "tuneaccunits"].set_text(_("degrees / second²"))
        elif d.units:
            w[axis + "tunedistunits"].set_text(_("mm"))
            w[axis + "tunevelunits"].set_text(_("mm / minute"))
            w[axis + "tuneaccunits"].set_text(_("mm / second²"))
        else:
            w[axis + "tunedistunits"].set_text(_("inches"))
            w[axis + "tunevelunits"].set_text(_("inches / minute"))
            w[axis + "tuneaccunits"].set_text(_("inches / second²"))
        w[axis+"tunevel"].set_value(float(w[axis+"maxvel"].get_text()))
        w[axis+"tuneacc"].set_value(float(w[axis+"maxacc"].get_text()))
        w[axis+"tunecurrentP"].set_value(w[axis+"P"].get_value())
        w[axis+"tuneorigP"].set_text("%s" % w[axis+"P"].get_value())
        w[axis+"tunecurrentI"].set_value(w[axis+"I"].get_value())
        w[axis+"tuneorigI"].set_text("%s" % w[axis+"I"].get_value())
        w[axis+"tunecurrentD"].set_value(w[axis+"D"].get_value())
        w[axis+"tuneorigD"].set_text("%s" % w[axis+"D"].get_value())
        w[axis+"tunecurrentFF0"].set_value(w[axis+"FF0"].get_value())
        w[axis+"tuneorigFF0"].set_text("%s" % w[axis+"FF0"].get_value())
        w[axis+"tunecurrentFF1"].set_value(w[axis+"FF1"].get_value())
        w[axis+"tuneorigFF1"].set_text("%s" % w[axis+"FF1"].get_value())
        w[axis+"tunecurrentFF2"].set_value(w[axis+"FF2"].get_value())
        w[axis+"tuneorigFF2"].set_text("%s" % w[axis+"FF2"].get_value())
        w[axis+"tunecurrentsteptime"].set_value(w[axis+"steptime"].get_value())
        w[axis+"tuneorigsteptime"].set_text("%s" % w[axis+"steptime"].get_value())
        w[axis+"tunecurrentstepspace"].set_value(float(w[axis+"stepspace"].get_text()))
        w[axis+"tuneorigstepspace"].set_text("%s" % w[axis+"stepspace"].get_value())
        w[axis+"tunecurrentdirhold"].set_value(float(w[axis+"dirhold"].get_text()))
        w[axis+"tuneorigdirhold"].set_text("%s" % w[axis+"dirhold"].get_value())
        w[axis+"tunecurrentdirsetup"].set_value(float(w[axis+"dirsetup"].get_text()))
        w[axis+"tuneorigdirsetup"].set_text("%s" % w[axis+"dirsetup"].get_value())
        self.tunejogplus = self.tunejogminus = 0
        w[axis+"tunedir"].set_active(0)
        w[axis+"tunerun"].set_active(0)
        w[axis+"tuneinvertmotor"].set_active(w[axis+"invertmotor"].get_active())
        w[axis+"tuneinvertencoder"].set_active(w[axis+"invertencoder"].get_active())
             
        self.halrun = halrun = os.popen("halrun -sf > /dev/null", "w")
        halrun.write("""
        loadrt threads period1=%(period)d name1=fast fp1=0 period2=%(period2)d name2=slow
        loadusr halscope
        loadrt steptest
        loadrt probe_parport
        loadrt hostmot2
        """ % {'period':100000, 'period2':self.data.servoperiod })    
        halrun.write("""
        loadrt hm2_pci config="firmware=hm2-trunk/%s/%s.BIT num_encoders=%d num_pwmgens=%d num_stepgens=%d" 
        addf hm2_%s.0.read slow
        addf steptest.0 slow
        addf hm2_%s.0.write slow
        addf hm2_%s.0.pet_watchdog fast
        """ % (board, firmware, self.data.numof_mesa_encodergens, self.data.numof_mesa_pwmgens, self.data.numof_mesa_stepgens, board,board,board))
        
        for concount,connector in enumerate(self.data.mesa_currentfirmwaredata[11]) :
            for pin in range (0,24):
                firmptype,compnum = self.data.mesa_currentfirmwaredata[12+pin+(concount*24)]
                pinv = 'm5i20c%(con)dpin%(num)dinv' % {'con':connector ,'num': pin}
                ptype = 'm5i20c%(con)dpin%(num)dtype' % {'con':connector ,'num': pin}
                pintype = self.widgets[ptype].get_active_text()
                pininv = self.widgets[pinv].get_active()
                truepinnum = (concount*24) + pin
                if pintype in (GPIOI,GPIOO,GPIOD): continue 
                # for encoder pins
                if pintype in (ENCA,ENCB,ENCI,ENCM):                                    
                    if not pintype == ENCA: continue                 
                    if pin == 3 :encpinnum = (connector-2)*4 
                    elif pin == 1 :encpinnum = 1+((connector-2)*4) 
                    elif pin == 15 :encpinnum = 2+((connector-2)*4) 
                    elif pin == 13 :encpinnum = 3+((connector-2)*4) 
                    halrun.write("net yellow_reset%d hm2_%s.0.encoder.%02d.reset \n"% (encpinnum,board,encpinnum))
                    halrun.write("net yellow_count%d hm2_%s.0.encoder.%02d.count \n"% (encpinnum,board,encpinnum))
                # for PWM pins
                elif pintype in (PWMP,PWMD,PWME,PDMP,PDMD,PDME):
                    if not pintype in (PWMP,PDMP): continue    
                    if pin == 7 :encpinnum = (connector-2)*4 
                    elif pin == 6 :encpinnum = 1 + ((connector-2)*4) 
                    elif pin == 19 :encpinnum = 2 + ((connector-2)*4) 
                    elif pin == 18 :encpinnum = 3 + ((connector-2)*4)        
                    halrun.write("net green_enable%d hm2_%s.0.pwmgen.%02d.enable \n"% (encpinnum,board,encpinnum)) 
                    halrun.write("net green_value%d hm2_%s.0.pwmgen.%02d.value \n"% (encpinnum,board,encpinnum)) 
                    halrun.write("setp hm2_%s.0.pwmgen.%02d.scale 10\n"% (board,encpinnum)) 
                # for Stepgen pins
                elif pintype in (STEPA,STEPB):
                    if not pintype == STEPA : 
                        continue    
                    if "m5i20" in stepgen:      
                        # check current component number to signal's component number  
                        if pin == int(stepgen[10:]):
                            self.currentstepgen = compnum
                            self.boardname = board
                            self.stepinvert = concount*24+1
                            halrun.write("setp hm2_%s.0.gpio.%03d.invert_output %d \n"% (board,self.stepinvert,w[axis+"invertmotor"].get_active()))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.step_type 0 \n"% (board,compnum))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.position-scale %f \n"% (board,compnum,float(w[axis + "scale"].get_text()) ))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.enable true \n"% (board,compnum))
                            halrun.write("net cmd steptest.0.position-cmd => hm2_%s.0.stepgen.%02d.position-cmd \n"% (board,compnum))
                            halrun.write("net feedback steptest.0.position-fb <= hm2_%s.0.stepgen.%02d.position-fb \n"% (board,compnum))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.steplen %d \n"% (board,compnum,w[axis+"steptime"].get_value()))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.stepspace %d \n"% (board,compnum,w[axis+"stepspace"].get_value()))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.dirhold %d \n"% (board,compnum,w[axis+"dirhold"].get_value()))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.dirsetup %d \n"% (board,compnum,w[axis+"dirsetup"].get_value()))
                            halrun.write("setp steptest.0.epsilon %f\n"% abs(1. / float(w[axis + "scale"].get_text()))  )
                            halrun.write("setp hm2_%s.0.stepgen.%02d.maxaccel 0 \n"% (board,compnum))
                            halrun.write("setp hm2_%s.0.stepgen.%02d.maxvel 0 \n"% (board,compnum))
                            halrun.write("loadusr halmeter pin hm2_%s.0.stepgen.%02d.velocity-fb -g 0 500\n"% (board,compnum))
                else: 
                    print "pintype error in mesa test panel method pintype:%s connector %d pin %d\n"% (pintype, connector,pin)

        temp = self.data.findsignal( "enable")
        amp = self.data.make_pinname(temp)
        if not amp == "false":
            if "HOSTMOT2" in amp:    
                amp = amp.replace("[HOSTMOT2](BOARD)",boardname) 
                halrun.write("setp %s true\n"% (amp + ".is_output"))             
                halrun.write("setp %s true\n"% (amp + ".out"))
                if self.data[temp+"inv"] == True:
                    halrun.write("setp %s true\n"%  (amp + ".invert_output"))

        temp = self.data.findsignal( "estop-out")
        estop = self.data.make_pinname(temp)
        if not estop =="false":        
            if "HOSTMOT2" in estop:
                estop = estop.replace("[HOSTMOT2](BOARD)",boardname) 
                halrun.write("setp %s true\n"%  (estop + ".is_output"))    
                halrun.write("setp %s true\n"%  (estop + ".out"))
                if self.data[temp+"inv"] == True:
                    halrun.write("setp %s true\n"%  (estop + ".invert_output"))

        halrun.write("start\n"); halrun.flush()
        w.servotunedialog.set_title(_("%s Axis Tune") % axis.upper())
        w.servotunedialog.show_all()
        self.widgets['window1'].set_sensitive(0)
        result = w.servotunedialog.run()
        w.servotunedialog.hide()
        if result == gtk.RESPONSE_OK:
            w[axis+"maxvel"].set_text("%s" % w[axis+"tunevel"].get_value())
            w[axis+"maxacc"].set_text("%s" % w[axis+"tuneacc"].get_value())
            w[axis+"P"].set_value( float(w[axis+"tunecurrentP"].get_text()))
            w[axis+"I"].set_value( float(w[axis+"tunecurrentI"].get_text()))
            w[axis+"D"].set_value( float(w[axis+"tunecurrentD"].get_text()))
            w[axis+"FF0"].set_value( float(w[axis+"tunecurrentFF0"].get_text()))
            w[axis+"FF1"].set_value( float(w[axis+"tunecurrentFF1"].get_text()))
            w[axis+"FF2"].set_value( float(w[axis+"tunecurrentFF2"].get_text()))
            w[axis+"steptime"].set_value(float(w[axis+"tunecurrentsteptime"].get_text()))
            w[axis+"stepspace"].set_value(float(w[axis+"tunecurrentstepspace"].get_text()))
            w[axis+"dirhold"].set_value(float(w[axis+"tunecurrentdirhold"].get_text()))
            w[axis+"dirsetup"].set_value(float(w[axis+"tunecurrentdirsetup"].get_text()))
            w[axis+"invertmotor"].set_active(w[axis+"tuneinvertmotor"].get_active())
            w[axis+"invertencoder"].set_active(w[axis+"tuneinvertencoder"].get_active())
        if not amp == "false":
             halrun.write("setp %s false\n"% (amp + ".out"))
        if not estop == "false":
             halrun.write("setp %s false\n"% (estop + ".out"))
        time.sleep(.001)   
        halrun.close()  
        self.widgets['window1'].set_sensitive(1)

    def update_tune_axis_params(self, *args):
        axis = self.axis_under_tune
        compnum = self.currentstepgen
        board = self.boardname
        if axis is None: return
        halrun = self.halrun
        halrun.write("""
            setp hm2_%(board)s.0.gpio.%(gpio)03d.invert_output %(invert)d 
            setp hm2_%(board)s.0.stepgen.%(num)02d.steplen %(len)d
            setp hm2_%(board)s.0.stepgen.%(num)02d.stepspace %(space)d
            setp hm2_%(board)s.0.stepgen.%(num)02d.dirhold %(hold)d
            setp hm2_%(board)s.0.stepgen.%(num)02d.dirsetup %(setup)d
            setp hm2_%(board)s.0.stepgen.%(num)02d.maxaccel %(accel)f
            setp hm2_%(board)s.0.stepgen.%(num)02d.maxvel %(velps)f
            setp steptest.0.jog-minus %(jogminus)s
            setp steptest.0.jog-plus %(jogplus)s
            setp steptest.0.run %(run)s
            setp steptest.0.amplitude %(amplitude)f
            setp steptest.0.maxvel %(velps)f
            setp steptest.0.maxaccel %(accel)f
            setp steptest.0.dir %(dir)s
            setp steptest.0.pause %(pause)d
        """ % {
            'gpio':self.stepinvert,
            'invert':self.widgets[axis+"tuneinvertmotor"].get_active(),
            'len':self.widgets[axis+"tunecurrentsteptime"].get_value(),
            'space':self.widgets[axis+"tunecurrentstepspace"].get_value(),
            'hold':self.widgets[axis+"tunecurrentdirhold"].get_value(),
            'setup':self.widgets[axis+"tunecurrentdirsetup"].get_value(),
            'board': board,
            'num': compnum,
            'jogminus': self.tunejogminus,
            'jogplus': self.tunejogplus,
            'run': self.widgets[axis+"tunerun"].get_active(),
            'amplitude': self.widgets[axis+"tuneamplitude"].get_value(),
            'accel': self.widgets[axis+"tuneacc"].get_value(),
            'vel': self.widgets[axis+"tunevel"].get_value(),
            'velps': (self.widgets[axis+"tunevel"].get_value()/60),
            'dir': self.widgets[axis+"tunedir"].get_active(),
            'pause':int(self.widgets[axis+"tunepause"].get_value()),
        })
        halrun.flush()

    def on_tunejogminus_pressed(self, w):
        self.tunejogminus = 1
        self.update_tune_axis_params()
    def on_tunejogminus_released(self, w):
        self.tunejogminus = 0
        self.update_tune_axis_params()
    def on_tunejogplus_pressed(self, w):
        self.tunejogplus = 1
        self.update_tune_axis_params()
    def on_tunejogplus_released(self, w):
        self.tunejogplus = 0
        self.update_tune_axis_params()
    def on_tuneinvertmotor_toggled(self, w):
        self.update_tune_axis_params()

    def test_axis(self, axis):
        data = self.data
        widgets = self.widgets
        axnum = "xyzas".index(axis)
        pump = False
        #step = axis + "step"
        #dir = axis + "dir"
        boardname = self.data.mesa_currentfirmwaredata[0]
        firmware = self.data.mesa_currentfirmwaredata[1]  
        fastdac = float(widgets["fastdac"].get_text())
        slowdac = float(widgets["slowdac"].get_text())
        dacspeed = widgets.Dac_speed_fast.get_active()
        
        if self.data.findsignal( (axis + "-pwm-pulse")) =="false" or self.data.findsignal( (axis + "-encoder-a")) =="false":
             self.warning_dialog( _(" You must designate a ENCODER signal and a PWM signal for this axis test") , True)     
             return
        if not self.data.findsignal("charge-pump") =="false": pump = True
   
        self.halrun = halrun = os.popen("halrun -sf > /dev/null", "w")       
        halrun.write("""loadrt threads period1=%(period)d name1=fast fp1=0 period2=%(period2)d name2=slow \n""" % {'period': 100000,'period2': self.data.servoperiod  })
        halrun.write("loadrt probe_parport\n")
        if self.data.number_pports>0:
            port3name = port2name = port1name = port3dir = port2dir = port1dir = ""
            if self.data.number_pports>2:
                 port3name = " " + self.data.ioaddr3
                 if self.data.pp3_direction:
                    port3dir =" out"
                 else: 
                    port3dir =" in"
            if self.data.number_pports>1:
                 port2name = " " + self.data.ioaddr2
                 if self.data.pp2_direction:
                    port2dir =" out"
                 else: 
                    port2dir =" in"
            port1name = self.data.ioaddr
            if self.data.pp1_direction:
               port1dir =" out"
            else: 
               port1dir =" in"
            halrun.write("loadrt hal_parport cfg=\"%s%s%s%s%s%s\"\n" % (port1name, port1dir, port2name, port2dir, port3name, port3dir))
        halrun.write("loadrt hostmot2\n")
        halrun.write("""loadrt hm2_pci config="firmware=hm2-trunk/%s/%s.BIT num_encoders=%d num_pwmgens=%d num_stepgens=%d"\n"""
         % (boardname, firmware, self.data.numof_mesa_encodergens, self.data.numof_mesa_pwmgens, self.data.numof_mesa_stepgens ))
        halrun.write("loadrt steptest\n")
        halrun.write("loadusr halmeter -g 0 500\n")
        halrun.write("loadusr halscope\n")
        halrun.write("addf hm2_%s.0.pet_watchdog fast\n"% boardname)
        halrun.write("addf hm2_%s.0.read slow\n"% boardname) 
        if pump:
            halrun.write( "loadrt charge_pump\n")
            halrun.write( "setp charge-pump.enable true\n")
            halrun.write( "net charge-pump <= charge-pump.out\n")
            halrun.write( "addf charge-pump slow\n")                 
        halrun.write("addf steptest.0 slow\n")
        halrun.write("addf hm2_%s.0.write slow\n"% boardname)     
        #halrun.write("addf parport.0.write fast")
        
        temp = self.data.findsignal( "enable")
        self.amp = self.data.make_pinname(temp)
        if not self.amp == "false":
            if "HOSTMOT2" in self.amp:    
                self.amp = self.amp.replace("[HOSTMOT2](BOARD)",boardname) 
                halrun.write("setp %s true\n"% (self.amp + ".is_output"))             
                halrun.write("setp %s false\n"% (self.amp + ".out"))
                if self.data[temp+"inv"] == True:
                    halrun.write("setp %s true\n"%  (self.amp + ".invert_output"))
                self.amp = self.amp + ".out"             
            if "parport" in self.amp:
                halrun.write("    setp %s true\n" % (self.amp ))
                if self.data[temp+"inv"] == True:
                    halrun.write("    setp %s true\n" % (self.amp + "-invert"))  
            halrun.write("loadusr halmeter -s pin %s -g 300 100 \n"%  (self.amp))         

        temp = self.data.findsignal( "estop-out")
        estop = self.data.make_pinname(temp)
        if not estop == "false":        
            if "HOSTMOT2" in estop:
                estop = estop.replace("[HOSTMOT2](BOARD)",boardname) 
                halrun.write("setp %s true\n"%  (estop + ".is_output"))    
                halrun.write("setp %s true\n"%  (estop + ".out"))
                if self.data[temp+"inv"] == True:
                    halrun.write("setp %s true\n"%  (estop + ".invert_output"))
                estop = estop + ".out"
            if "parport" in estop:
                halrun.write("    setp %s true\n" % (estop))
                if self.data[temp+"inv"] == True:
                    halrun.write("    setp %s true\n" % (estop + "-invert"))  
            halrun.write("loadusr halmeter -s pin %s -g 300 50 \n"%  (estop)) 
    
        temp = self.data.findsignal( "charge-pump")
        pump = self.data.make_pinname(temp)
        if not pump == "false":        
            if "HOSTMOT2" in pump:
                pump = pump.replace("[HOSTMOT2](BOARD)",boardname) 
                halrun.write("setp %s true\n"%  (pump + ".is_output"))    
                #halrun.write("setp %s true\n"%  (pump + ".out"))
                if self.data[temp+"inv"] == True:
                    halrun.write("setp %s true\n"%  (pump + ".invert_output"))
                pump = pump + ".out"              
            if "parport" in pump:
                halrun.write("    setp %s true\n" % (pump))
                if self.data[temp+"inv"] == True:
                    halrun.write("    setp %s true\n" % (pump + "-invert"))  
            halrun.write( "net charge-pump %s\n"%(pump))
            halrun.write("loadusr halmeter -s pin %s -g 300 0 \n"%  (pump))             

        pwm = self.data.make_pinname(self.data.findsignal( (axis + "-pwm-pulse")))
        if not pwm == "false":        
            if "HOSTMOT2" in pwm:
                pwm = pwm.replace("[HOSTMOT2](BOARD)",boardname)     
                halrun.write("net dac %s \n"%  (pwm +".value"))
                halrun.write("setp %s \n"%  (pwm +".enable true"))
                halrun.write("setp %s \n"%  (pwm +".scale 10"))
                halrun.write("loadusr halmeter -s pin %s -g 300 150\n"%  (pwm +".value"))
            
        self.enc = self.data.make_pinname(self.data.findsignal( (axis + "-encoder-a")))
        if not self.enc =="false":        
            if "HOSTMOT2" in self.enc:
                self.enc = self.enc.replace("[HOSTMOT2](BOARD)",boardname)     
                halrun.write("net enc-reset %s \n"%  (self.enc +".reset"))
                halrun.write("setp %s 1\n"%  (self.enc +".scale"))
                halrun.write("setp %s \n"%  (self.enc +".filter true"))
                halrun.write("loadusr halmeter -s pin %s -g 300 200\n"%  (self.enc +".position"))
                halrun.write("loadusr halmeter -s pin %s -g 300 250\n"%  (self.enc +".velocity"))
        
        widgets.openloopdialog.set_title(_("%s Axis Test") % axis.upper())
        self.jogplus = self.jogminus = self.enc_reset = self.enable_amp = 0
        self.enc_scale = 1
        self.axis_under_test = axis
        widgets.testinvertmotor.set_active(widgets[axis+"invertmotor"].get_active())
        widgets.testinvertencoder.set_active(widgets[axis+"invertencoder"].get_active())
        widgets.testoutputoffset.set_value(widgets[axis+"outputoffset"].get_value())
        self.update_axis_params()      
        halrun.write("start\n"); halrun.flush()
        self.widgets['window1'].set_sensitive(0)
        self.widgets.jogminus.set_sensitive(0)
        self.widgets.jogplus.set_sensitive(0)
        widgets.openloopdialog.show_all()
        result = widgets.openloopdialog.run()

        widgets.openloopdialog.hide()
        if not self.amp == "false":
             halrun.write("setp %s false\n"% (self.amp))
        if not estop == "false":
             halrun.write("setp %s false\n"% (estop))
        time.sleep(.001)
        halrun.close()        
        if result == gtk.RESPONSE_OK:
            #widgets[axis+"maxacc"].set_text("%s" % widgets.testacc.get_value())
            widgets[axis+"invertmotor"].set_active(widgets.testinvertmotor.get_active())
            widgets[axis+"invertencoder"].set_active(widgets.testinvertencoder.get_active())
            widgets[axis+"outputoffset"].set_value(widgets.testoutputoffset.get_value())
            #widgets[axis+"maxvel"].set_text("%s" % widgets.testvel.get_value())
        self.axis_under_test = None
        self.widgets['window1'].set_sensitive(1)
    
    def update_axis_params(self, *args):
        axis = self.axis_under_test
        if axis is None: return
        halrun = self.halrun
        if self.widgets.Dac_speed_fast.get_active() == True:output = float(self.widgets.fastdac.get_text())
        else: output = float(self.widgets.slowdac.get_text())
        if self.jogminus == 1:output = output * -1
        elif not self.jogplus == 1:output = 0
        if self.widgets.testinvertmotor.get_active() == True: output = output * -1
        output += float(self.widgets.testoutputoffset.get_text())
        if not self.amp == "false":
            halrun.write("setp %s %d\n"% (self.amp, self.enable_amp))
        halrun.write("""setp %(scalepin)s.scale %(scale)d\n""" % { 'scalepin':self.enc, 'scale': self.enc_scale})
        halrun.write("""sets dac %(output)f\n""" % { 'output': output})
        halrun.write("""sets enc-reset %(reset)d\n""" % { 'reset': self.enc_reset})
        halrun.flush()

    def on_jogminus_pressed(self, w):
        self.jogminus = 1
        self.update_axis_params()
    def on_jogminus_released(self, w):
        self.jogminus = 0
        self.update_axis_params()
    def on_jogplus_pressed(self, w):
        self.jogplus = 1
        self.update_axis_params()
    def on_jogplus_released(self, w):
        self.jogplus = 0
        self.update_axis_params()
    def on_resetbutton_pressed(self, w):
        self.enc_reset = 1
        self.update_axis_params()
    def on_resetbutton_released(self, w):
        self.enc_reset = 0
        self.update_axis_params()
    def on_testinvertmotor_toggled(self, w):
        self.update_axis_params()
    def on_testinvertencoder_toggled(self, w):
        self.enc_scale = self.enc_scale * -1
        self.update_axis_params()
    def on_testoutputoffset_value_changed(self, w):
        self.update_axis_params()
    def on_enableamp_toggled(self, w):
        self.enable_amp = self.enable_amp * -1 + 1
        self.widgets.jogminus.set_sensitive(self.enable_amp)
        self.widgets.jogplus.set_sensitive(self.enable_amp)
        self.update_axis_params()

    def run(self, filename=None):
        if filename is not None:
            self.data.load(filename, self)
            self.widgets.druid1.set_page(self.widgets.basicinfo)
        gtk.main()
   
    

def makedirs(d):
    try:
        os.makedirs(d)
    except os.error, detail:
        if detail.errno != errno.EEXIST: raise
makedirs(os.path.expanduser("~/emc2/configs"))

opts, args = getopt.getopt(sys.argv[1:], "fr")
mode = 0
force = 0
for k, v in opts:
    if k == "-r": mode = 1
    if k == "-f": force = 1

if mode:
    filename = args[0]
    data = Data()
    data.load(filename, None, force)
    data.save()
elif args:
    app = App()
    app.run(args[0])
else:
    app = App()
    app.run()
