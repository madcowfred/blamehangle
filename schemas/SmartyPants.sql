CREATE TABLE factoids (
    name character varying(64) NOT NULL,
    value text NOT NULL,
    author_nick character varying(32),
    author_host character varying(128),
    modifier_nick character varying(32),
    modifier_host character varying(128),
    requester_nick character varying(32),
    requester_host character varying(128),
    request_count integer DEFAULT 0 NOT NULL,
    locker_nick character varying(32),
    locker_host character varying(128),
    created_time integer,
    modified_time integer,
    requested_time integer,
    locked_time integer,
    PRIMARY KEY (name)
);
