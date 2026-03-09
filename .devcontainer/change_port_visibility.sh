#!/bin/bash
# Change port visibility after codespace creation
gh codespace ports visibility 6080:public -c $CODESPACE_NAME
gh codespace ports visibility 5901:public -c $CODESPACE_NAME   