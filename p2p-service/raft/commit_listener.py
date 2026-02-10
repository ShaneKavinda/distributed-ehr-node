from node import RaftLogEntry

class CommitListener:
    def on_commit(self, entry: RaftLogEntry)-> None:
        '''
        Docstring for on_commit

        Publish an internal signal to the Dispatcher to add the command to the Message Queue.

        e.g.
        def on_commit(entry):
            executor.submit(publish_to_mq, entry)

        
        :param self: Description
        :param entry: Description
        :type entry: RaftLogEntry
        '''