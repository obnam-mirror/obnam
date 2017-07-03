# Copyright 2014-2015  Lars Wirzenius
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-3+ =*=


TITLE_EN = Backups with Obnam
TITLE_DE = Backups mit Obnam
TRANS_DE = Übersetzung: Jan Niggemann (jn@hz6.de)
TITLE_FR = Sauvegardes avec Obnam
TRANS_FR = Traduction : Pierrick Martinez, Remi Rampin
AUTHOR = Lars Wirzenius (liw@liw.fi)
VERSION = Version $(shell git describe || python ../setup.py --version)

en_sources = $(shell ls en/*.mdwn)
fr_sources = $(shell ls fr/*.mdwn)
de_sources = $(shell ls de/*.mdwn)
pdfs = \
	obnam-manual.en.pdf \
	obnam-manual.fr.pdf \
	obnam-manual.de.pdf
htmls = \
	obnam-manual.en.html \
	obnam-manual.fr.html \
	obnam-manual.de.html

all: html pdf

html: $(htmls)

pdf: $(pdfs)

obnam-manual.en.pdf: Makefile $(en_sources)
	./format-pdf $@ \
		"$(TITLE_DE)" "$(AUTHOR)" "$(VERSION)" "english" "" \
		$(en_sources)

obnam-manual.en.html: Makefile $(en_sources) ../obnam.css
	./format-html $@ \
		"$(TITLE_DE)" "$(AUTHOR)" "$(VERSION)" "english" "" \
		$(en_sources)

obnam-manual.fr.pdf: Makefile $(fr_sources)
	./format-pdf $@ \
		"$(TITLE_DE)" "$(AUTHOR)" "$(VERSION)" "french" "$(TRANS_FR)" \
		$(fr_sources)

obnam-manual.fr.html: Makefile $(fr_sources) ../obnam.css
	./format-html $@ \
		"$(TITLE_FR)" "$(AUTHOR)" "$(VERSION)" "french" "$(TRANS_FR)" \
		$(fr_sources)

obnam-manual.de.pdf: Makefile $(de_sources)
	./format-pdf $@ \
		"$(TITLE_DE)" "$(AUTHOR)" "$(VERSION)" "german" "$(TRANS_DE)" \
		$(de_sources)

obnam-manual.de.html: Makefile $(de_sources) ../obnam.css
	./format-html $@ \
		"$(TITLE_DE)" "$(AUTHOR)" "$(VERSION)" "german" "$(TRANS_DE)" \
		$(de_sources)

clean:
	rm -f $(outputs) en/000.mdwn
	rm -f $(outputs) de/000.mdwn
	rm -f $(outputs) fr/000.mdwn
