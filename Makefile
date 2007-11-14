VERSION = 0.5.2

doc: HEADER.html

HEADER.html: README
	ln -s README HEADER.txt
	asciidoc -a toc -a numbered -a sectids HEADER.txt
	rm HEADER.txt

dist:
	git-archive --format=tar --prefix=pyrssi-$(VERSION)/ HEAD > pyrssi-$(VERSION).tar
	mkdir -p pyrssi-$(VERSION)
	git log --no-merges |git name-rev --tags --stdin > pyrssi-$(VERSION)/Changelog
	tar rf pyrssi-$(VERSION).tar pyrssi-$(VERSION)/Changelog
	rm -rf pyrssi-$(VERSION)
	gzip -f -9 pyrssi-$(VERSION).tar

release:
	git tag -l |grep -q $(VERSION) || git tag -a -m $(VERSION) $(VERSION)
	$(MAKE) dist
