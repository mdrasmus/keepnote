# Distributed under the terms of the GNU General Public License v2
# $Header: $
EAPI=3

PYTHON_DEPEND="2:2.5"
PYTHON_USE_WITH="sqlite"
inherit distutils python 


DESCRIPTION="a note taking application"
HOMEPAGE="http://keepnote.org/"
SRC_URI="http://keepnote.org/download-test/${P}.tar.gz"

LICENSE="GPL-2"
KEYWORDS="amd64 ~ppc64 ~sparc x86 ppc"
SLOT="0"
IUSE="spell"

DEPEND=">=dev-python/pygtk-2.12.0
       spell? ( >=app-text/gtkspell-2.0.11-r1 )"

RDEPEND="${DEPEND}"

DOCS="CHANGES README"
