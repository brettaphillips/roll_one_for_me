#!/usr/bin/env python3

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Union, Tuple

from praw.models import Comment, Submission, Message

from rofm.classes.core.worknodes.rofm_core import Worknode, WorkloadType
from rofm.classes.core.worknodes.rofm_rollers import RollTable
from rofm.classes.html_parsers import CMSParser, get_links_from_text
from rofm.classes.reddit import Reddit
from rofm.classes.util.misc import get_html_from_cms

logging.getLogger().setLevel(logging.DEBUG)


@dataclass
class TopLevelComments(Worknode):
    args: List[Comment]
    kwargs: Dict[str, Any] = field(default_factory=dict)

    workload_type: WorkloadType = WorkloadType.parse_top_level_comments
    _name: str = "Top level comment parser"

    def _my_work_resolver(self):
        for i, comment in enumerate(self.args):
            new_work = Comment(comment)
            new_work.metadata = {'index': i, 'source': 'Comment'}
            self.additional_work.append(new_work)

    def __str__(self):
        return "\n\n\n".join((str(work) for work in self.additional_work if str(work)))

    def __repr__(self):
        return super(TopLevelComments, self).__repr__()


@dataclass
class MixedType(Worknode):
    args: Union[Comment, Submission, Message]
    kwargs: Dict[str, Any] = field(default_factory=dict)

    workload_type: WorkloadType = WorkloadType.parse_item_for_tables
    name: str = "Parse item of unidentified type"

    def __str__(self):
        return "\n\n".join(str(c) for c in self.children)

    def __repr__(self):
        return super(MixedType, self).__repr__()

    def _my_work_resolver(self):
        parsed_tables = CMSParser(self.args, auto_parse=True).tables
        if not parsed_tables:
            return "No tables found"

        for table in parsed_tables:
            self.additional_work.append(RollTable(table))


@dataclass
class Comment(MixedType):
    args: Comment
    name: str = "Comment parser"

    def __str__(self):
        return super(Comment, self).__str__()

    def __repr__(self):
        return super(Comment, self).__repr__()


@dataclass
class Submission(MixedType):
    args: Submission
    name: str = "Submission parser"

    def __str__(self):
        return super(Submission, self).__str__()

    def __repr__(self):
        return super(Submission, self).__repr__()


@dataclass
class Message(MixedType):
    args: Message
    name: str = "Private message parser"

    def __str__(self):
        return super(Message, self).__str__()

    def __repr__(self):
        return super(Message, self).__repr__()


@dataclass
class RedditDomainUrls(Worknode):
    args: Union[Comment, Submission, Message]
    kwargs: Dict[str, Any] = field(default_factory=dict)

    workload_type: WorkloadType = WorkloadType.parse_for_reddit_domain_urls
    name: str = "Search for Reddit urls"

    def __str__(self):
        return "\n\n\n".join((str(work) for work in self.additional_work if str(work)))

    def __repr__(self):
        return super(RedditDomainUrls, self).__repr__()

    def _my_work_resolver(self):
        html_text = get_html_from_cms(self.args)
        reddit_links = get_links_from_text(html_text, 'reddit.com')

        if not reddit_links:
            return "No links found"

        for link in reddit_links:
            self.additional_work.append(FollowLink(link))


@dataclass
class SpecialRequest(Worknode):
    args: Union[Comment, Submission, Message]
    kwargs: Dict[str, Any] = field(default_factory=dict)

    workload_type: WorkloadType = WorkloadType.parse_for_special_requests
    name: str = "Search for Reddit urls"

    def __str__(self):
        raise NotImplementedError("Special requests not yet implemented.")

    def __repr__(self):
        return super(SpecialRequest, self).__repr__()

    def _my_work_resolver(self):
        raise NotImplementedError("Special requests not yet implemented.")


@dataclass
class FollowLink(Worknode):
    args: Tuple[str, str]  # text, href
    kwargs: Dict[str, Any] = field(default_factory=dict)

    # populated in post-init
    text: str = None
    href: str = None

    workload_type: WorkloadType = WorkloadType.follow_link
    name: str = "Consider following url"

    def __post_init__(self):
        self.text, self.href = self.args

    def __str__(self):
        if self.additional_work:
            return f"From your link [{self.text}]({self.href}):\n\n{self.additional_work[0]}"
        return (f"Your link [{self.text}]({self.href}] doesn't resolve for me, possibly because it's not on Reddit."
                f"  I don't like to wander too far from home, sorry.")

    def __repr__(self):
        return super(FollowLink, self).__repr__()

    def _my_work_resolver(self):
        _, link_href = self.args
        reddit_item = Reddit.try_to_follow_link(link_href)
        if reddit_item is None:
            return "Refusing to follow non-Reddit link."

        self.additional_work = [MixedType(reddit_item)]
