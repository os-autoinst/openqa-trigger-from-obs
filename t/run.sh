cd "$(dirname "${BASH_SOURCE[0]}")"

pass=0
fail=0

for dir in *; do
    [ -d "$dir" ] || continue
    [ "$dir" != docker ] || continue

    for subdir in $dir/*/; do
        # if no subdir - execute body only once
        [ -d "$subdir" ] || subdir=$dir

        # run general checks
        for file in test*.sh; do
            [ -f "$file" ] || continue
           out=$(bash -e "$file" "$subdir" 2>&1)
            if [ $? -eq 0 ] ; then
                : $((pass++))
                echo "P:$subdir $file"
            else
                : $((fail++))
                echo "F-$subdir $file:$out"
            fi
        done
        # if no subdir - execute body only once
        [ "$subdir" != "$dir" ] || break
    done

    # run product specific checks
    for file in "$dir"/test*.sh; do
        [ -f "$file" ] || continue
        out=$(bash -e "$file" 2>&1)
        if [ $? -eq 0 ] ; then
            : $((pass++))
            echo "P:$file"
        else
            : $((fail++))
            echo "F-$file:$out"
        fi
    done
done

(
dockerfail=0
cd docker
for t in *.sh; do
    [ -x "$t" ] || continue
    ./$t
    if [ $? -eq 0 ] ; then
        echo "P:$t"
    else
        : $((dockerfail++))
        echo "F-$t"
    fi
done
exit $dockerfail
)
dockerfail=$?
( exit $((fail + dockerfail))  )
