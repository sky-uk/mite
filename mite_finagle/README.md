# mite_finagle

Infrastructure for injecting load into finagle services with mite: the thrift
binary RPC format wrapped in finagleʼs mux framing protocol.

Install: `pip install mite[finagle]`

Full documentation:
https://github.com/sky-uk/mite/blob/master/docs/plugins/finagle.md

The TODO list below is kept here rather than in the published documentation,
as it is a maintainer backlog rather than reference material.

## TODOs / future extension

### Implicit connection cache

(an idea that just occurred to me while writing these docs, sigh)

One thing we could do, rather than exposing the finagle connection in
the way that this code does, is to enable an implicit process-level
connection pool.  Then we could write the finagle journeys just like we
write the http ones, but get the desired connection reuse behavior that
we want to simulate the finagle protocol.

### Better/more complete integration suite

What it says in the title

### Better unit test coverage

What it says in the title

### Performance tests/characterization of the finagle code

What it says in the title

### Finish the reply object implemetation

The reply yielding code works OK when the reply is a thrift object and
(I hope – test this) `void`.  What is missing is:
- tests for the handling of int, list, etc return
- `chained_wait` for non-object returns

### Smarter handling of method arguments

Currently if we have a thrift method that takes lots of custom types in
its arguments, we need to import all those from the thrift generated
code, and construct them ourselves.  Do we want to implement some sort
of clever coercion so that dicts (etc) can be transformed into the right
objects?  We have all the info we need to do this; itʼs just not plumbed
up (and idk if tiʼs a good idea or not).
