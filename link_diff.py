import sys


def find_dff_between_files(file_name1, file_name2):
    matching_url = set()
    unmatched_url = set()

    with open(file_name1, "r") as file1:
        for line1 in file1:
            match_found = False
            with open(file_name2, "r") as file2:
                for line2 in file2:
                    if line1 == line2:
                        matching_url.add(line1)
                        match_found = True
                        break
                if match_found:
                    continue
                else:
                    unmatched_url.add(line1)

    return matching_url, unmatched_url


if __name__ == "__main__":
    file_name1 = sys.argv[1]
    file_name2 = sys.argv[2]

    matching_url, unmatched_url = find_dff_between_files(file_name1, file_name2)
    print("unmatched urls between {} and {} ".format(file_name1, file_name2))
    for url in unmatched_url:
        print(url)

    matching_url, unmatched_url = find_dff_between_files(file_name2, file_name1)
    print("unmatched urls between {} and {} ".format(file_name2, file_name1))
    for url in unmatched_url:
        print(url)
