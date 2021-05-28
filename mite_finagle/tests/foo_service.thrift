# thrift --gen py foo_service.thrift; mv gen-py/foo_service .; rm -r gen-py

struct FooRequest {
    1: required string mystring;
}

struct FooResponse {
    1: required string responsestring;
}

service Foo {
    FooResponse performfoo(1: FooRequest request);
}
