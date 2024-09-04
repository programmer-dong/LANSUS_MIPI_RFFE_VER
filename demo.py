def generate_mask_strings(bit_range_lists):  
    mask_strings = ""
    read_and = "11111111"
    list_data = list(read_and)
    for each_reserved in bit_range_lists:
        if ":" not in each_reserved:
            list_data[int(each_reserved)] = '0'
        elif ":" in each_reserved:
            high_bit = int(each_reserved.split(":")[0]) + 1
            low_bit = int(each_reserved.split(":")[1])
            for index_change in range(low_bit, high_bit):
                print("debug_number:", index_change)
                list_data[index_change] = '0' 
    # 逆序列表  
    reversed_lst = list_data[::-1]  
    
    # 将逆序后的列表转换为一个字符串  
    reversed_str = ''.join(reversed_lst)  
    return "&8'b" + reversed_str
  
# 示例使用  
bit_range_lists = ['7:6', "4:3", '1']  
mask_strings = generate_mask_strings(bit_range_lists)  

print(mask_strings)