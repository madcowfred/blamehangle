CREATE TABLE factoids (
    name character varying(64) NOT NULL,
    value text NOT NULL,
    author_nick character varying(64),
    author_host character varying(192),
    modifier_nick character varying(64),
    modifier_host character varying(192),
    requester_nick character varying(64),
    requester_host character varying(192),
    request_count integer DEFAULT 0 NOT NULL,
    locker_nick character varying(64),
    locker_host character varying(192),
    created_time integer,
    modified_time integer,
    requested_time integer,
    locked_time integer,
    PRIMARY KEY (name)
);
