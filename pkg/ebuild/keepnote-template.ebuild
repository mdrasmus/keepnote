# Distributed under the terms of the GNU General Public License v2
# $Header: $

inherit distutils

EAPI=2

DESCRIPTION="a note taking application"
HOMEPAGE="http://keepnote.org/keepnote/"
SRC_URI="http://keepnote.org/keepnote/download/${P}.tar.gz"

LICENSE="GPL-2"
KEYWORDS="amd64 ~ppc64 ~sparc x86 ppc"
SLOT="0"
IUSE="spell"

DEPEND=">=virtual/python-2.5[sqlite]
       >=dev-python/pygtk-2.12.0
       spell? ( >=app-text/gtkspell-2.0.11-r1 )"

RDEPEND="${DEPEND}"

DOCS="CHANGES README"
